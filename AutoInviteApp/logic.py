# logic.py
import os
import time
import logging
import threading
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from queue import Queue
from types import SimpleNamespace
import re
import traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import vrchatapi
from vrchatapi.api import authentication_api, groups_api, users_api, worlds_api
from vrchatapi.exceptions import ApiException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
from vrchatapi.models.create_group_invite_request import CreateGroupInviteRequest

logger = logging.getLogger("VRChatAutoInvite.Logic")

class VRChatLogWatcher(FileSystemEventHandler):
    """Watches the VRChat log file for changes and processes new lines in real-time"""
    
    def __init__(self, logic_controller):
        self.logic = logic_controller
        self.log_path = None
        self.observer = None
        self.file_position = 0
        self.is_watching = False
        self.watch_thread = None
        self.current_instance = None
        self.player_events = {}  # Dictionary to track player events by ID
        
    def start_watching(self, log_path=None, scan_existing=True):
        """Start watching the VRChat log file
        
        Args:
            log_path: Path to the log file to watch. If None, will find the latest log file.
            scan_existing: Whether to scan the existing log file for player data.
        """
        if self.is_watching:
            self.logic.log("Already watching log file")
            return False
            
        # Find the log file if not provided
        if not log_path:
            log_path = self.logic._get_vrchat_log_path()
            
        if not log_path or not os.path.exists(log_path):
            self.logic.log("Could not find VRChat log file to watch")
            return False
            
        self.log_path = log_path
        self.logic.log(f"Starting to watch log file: {log_path}")
        
        # Process existing content if requested
        if scan_existing:
            self.logic.log("Performing full scan of existing log file...")
            self._scan_entire_log()
        else:
            # Just position at the end of the file without scanning
            self._position_at_end()
        
        # Start watching for changes
        self.is_watching = True
        self.watch_thread = threading.Thread(target=self._watch_log, daemon=True)
        self.watch_thread.start()
        
        self.logic.log("Log watcher started successfully")
        return True
        
    def _position_at_end(self):
        """Position at the end of the log file without scanning"""
        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Go to the end of the file
                f.seek(0, os.SEEK_END)
                self.file_position = f.tell()
                
            self.logic.log(f"Positioned at end of log file (position {self.file_position})")
        except Exception as e:
            self.logic.log(f"Error positioning at end of log file: {str(e)}")
            
    def _scan_entire_log(self):
        """Scan the entire log file for instance and player information"""
        try:
            self.logic.log("Scanning entire log file for instance and player information...")
            
            # First find the current instance
            self._find_current_instance()
            
            if not self.current_instance:
                self.logic.log("Could not find current instance in logs, will only monitor new entries")
                self._position_at_end()
                return
                
            # Now scan for player join/leave events
            self.logic.log(f"Scanning for player events in instance {self.current_instance}...")
            
            # Track instance changes and player events
            instance_changes = []  # List of (timestamp, instance_id) tuples
            
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            # First pass: find all instance changes
            for line in lines:
                if "Joining" in line and "Room" in line:
                    timestamp_match = re.search(r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})', line)
                    
                    # Try different patterns for instance ID
                    instance_patterns = [
                        r'Joining or Creating Room:\s+(\S+)',
                        r'Joining Room:\s+(\S+)',
                        r'Room:\s+(\S+)',
                        r'Joining\s+(\S+)'
                    ]
                    
                    instance_id_found = None
                    for pattern in instance_patterns:
                        instance_match = re.search(pattern, line)
                        if instance_match:
                            instance_id_found = instance_match.group(1).strip()
                            break
                    
                    if timestamp_match and instance_id_found:
                        timestamp_str = timestamp_match.group(1)
                        timestamp = datetime.strptime(timestamp_str, '%Y.%m.%d %H:%M:%S')
                        instance_changes.append((timestamp, instance_id_found))
            
            # Sort instance changes by timestamp
            instance_changes.sort(key=lambda x: x[0])
            
            # Find the most recent instance change
            if instance_changes:
                most_recent = instance_changes[-1]
                self.current_instance = most_recent[1]
                instance_change_time = most_recent[0]
                self.logic.log(f"Most recent instance: {self.current_instance} (changed at {instance_change_time})")
                
                # Second pass: process player events after the most recent instance change
                for line in lines:
                    timestamp_match = re.search(r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})', line)
                    if not timestamp_match:
                        continue
                        
                    timestamp_str = timestamp_match.group(1)
                    timestamp = datetime.strptime(timestamp_str, '%Y.%m.%d %H:%M:%S')
                    
                    # Skip events before the instance change
                    if timestamp < instance_change_time:
                        continue
                        
                    # Process this line for player events
                    self._process_log_line(line)
            
            # Position at the end of the file for future monitoring
            self._position_at_end()
            
            # Log summary of active players
            active_players, _ = self.get_active_players()
            if active_players:
                self.logic.log(f"Initial scan found {len(active_players)} active players in instance {self.current_instance}")
                for player in active_players:
                    if player.id in self.logic._player_join_times:
                        join_time = self.logic._player_join_times[player.id]
                        time_in_instance = (datetime.now() - join_time).total_seconds()
                        self.logic.log(f"  - {player.display_name} ({player.id}): in instance for {time_in_instance:.1f} seconds")
            else:
                self.logic.log(f"Initial scan found no active players in instance {self.current_instance}")
                
        except Exception as e:
            self.logic.log(f"Error scanning log file: {str(e)}")
            self.logic.log(f"Exception details: {traceback.format_exc()}")
            # Position at the end of the file anyway
            self._position_at_end()
        
    def stop_watching(self):
        """Stop watching the VRChat log file"""
        if not self.is_watching:
            return
            
        self.is_watching = False
        if self.observer:
            self.observer.stop()
            self.observer = None
            
        if self.watch_thread and self.watch_thread.is_alive():
            self.watch_thread.join(timeout=1.0)
            
        self.logic.log("Stopped watching log file")
        
    def _find_current_instance(self):
        """Scan the log file to find the current instance"""
        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            # Process lines in reverse to find the most recent instance
            for line in reversed(lines):
                if "Joining" in line and "Room" in line:
                    timestamp_match = re.search(r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})', line)
                    
                    # Try different patterns for instance ID
                    instance_patterns = [
                        r'Joining or Creating Room:\s+(\S+)',
                        r'Joining Room:\s+(\S+)',
                        r'Room:\s+(\S+)',
                        r'Joining\s+(\S+)'
                    ]
                    
                    instance_id_found = None
                    for pattern in instance_patterns:
                        instance_match = re.search(pattern, line)
                        if instance_match:
                            instance_id_found = instance_match.group(1).strip()
                            break
                    
                    if timestamp_match and instance_id_found:
                        timestamp_str = timestamp_match.group(1)
                        self.current_instance = instance_id_found
                        self.logic.log(f"Found current instance in logs: {self.current_instance} (from {timestamp_str})")
                        return
                        
            self.logic.log("Could not find current instance in logs")
            
        except Exception as e:
            self.logic.log(f"Error finding current instance: {str(e)}")
            
    def _watch_log(self):
        """Watch the log file for changes and process new lines"""
        try:
            while self.is_watching:
                if os.path.exists(self.log_path):
                    # Check if file has been modified
                    current_size = os.path.getsize(self.log_path)
                    
                    if current_size > self.file_position:
                        # File has grown, process new content
                        with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                            f.seek(self.file_position)
                            new_lines = f.readlines()
                            self.file_position = f.tell()
                            
                        # Process each new line
                        for line in new_lines:
                            self._process_log_line(line)
                            
                # Sleep briefly to avoid high CPU usage
                time.sleep(0.1)
                
        except Exception as e:
            self.logic.log(f"Error watching log file: {str(e)}")
            self.is_watching = False
            
    def _process_log_line(self, line):
        """Process a single line from the log file"""
        try:
            # Check for instance change
            if "Joining" in line and "Room" in line:
                timestamp_match = re.search(r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})', line)
                
                # Try different patterns for instance ID
                instance_patterns = [
                    r'Joining or Creating Room:\s+(\S+)',
                    r'Joining Room:\s+(\S+)',
                    r'Room:\s+(\S+)',
                    r'Joining\s+(\S+)'
                ]
                
                instance_id_found = None
                for pattern in instance_patterns:
                    instance_match = re.search(pattern, line)
                    if instance_match:
                        instance_id_found = instance_match.group(1).strip()
                        break
                
                if timestamp_match and instance_id_found:
                    timestamp_str = timestamp_match.group(1)
                    self.current_instance = instance_id_found
                    self.logic.log(f"Instance changed to: {self.current_instance} (at {timestamp_str})")
                    
                    # Clear player events when instance changes
                    self.player_events = {}
                    
                    # Notify the logic controller of the instance change
                    if hasattr(self.logic, 'on_instance_change'):
                        self.logic.on_instance_change(self.current_instance)
                    
            # Check for player join events
            elif "[Behaviour] OnPlayerJoined" in line:
                timestamp_match = re.search(r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})', line)
                player_match = re.search(r'OnPlayerJoined\s+(\S+)\s+\((\S+)\)', line)
                
                if timestamp_match and player_match:
                    timestamp_str = timestamp_match.group(1)
                    player_name = player_match.group(1).strip()
                    player_id = player_match.group(2).strip()
                    timestamp = datetime.strptime(timestamp_str, '%Y.%m.%d %H:%M:%S')
                    
                    # Record the join event
                    if player_id not in self.player_events:
                        self.player_events[player_id] = {
                            'name': player_name,
                            'joins': [],
                            'leaves': []
                        }
                    
                    self.player_events[player_id]['joins'].append(timestamp)
                    self.logic.log(f"Player joined: {player_name} ({player_id}) at {timestamp_str}")
                    
                    # Notify the logic controller of the player join
                    if hasattr(self.logic, 'on_player_join'):
                        self.logic.on_player_join(player_id, player_name, timestamp)
                    
            # Check for player leave events
            elif "[Behaviour] OnPlayerLeft" in line:
                timestamp_match = re.search(r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})', line)
                player_match = re.search(r'OnPlayerLeft\s+(\S+)\s+\((\S+)\)', line)
                
                if timestamp_match and player_match:
                    timestamp_str = timestamp_match.group(1)
                    player_name = player_match.group(1).strip()
                    player_id = player_match.group(2).strip()
                    timestamp = datetime.strptime(timestamp_str, '%Y.%m.%d %H:%M:%S')
                    
                    # Record the leave event
                    if player_id not in self.player_events:
                        self.player_events[player_id] = {
                            'name': player_name,
                            'joins': [],
                            'leaves': []
                        }
                    
                    self.player_events[player_id]['leaves'].append(timestamp)
                    self.logic.log(f"Player left: {player_name} ({player_id}) at {timestamp_str}")
                    
                    # Notify the logic controller of the player leave
                    if hasattr(self.logic, 'on_player_leave'):
                        self.logic.on_player_leave(player_id, player_name, timestamp)
                    
        except Exception as e:
            self.logic.log(f"Error processing log line: {str(e)}")
            
    def get_active_players(self):
        """Get a list of active players in the current instance"""
        active_players = []
        player_join_times = {}
        
        for player_id, events in self.player_events.items():
            # If there are more joins than leaves, the player is still in the instance
            if len(events['joins']) > len(events['leaves']):
                # Use the most recent join time
                latest_join = max(events['joins'])
                
                # Create player object
                player = SimpleNamespace(
                    id=player_id,
                    display_name=events['name']
                )
                
                active_players.append(player)
                player_join_times[player_id] = latest_join
        
        return active_players, player_join_times

class VRChatLogic:
    def __init__(self, config_manager=None, plugin_manager=None):
        self.api_client = None
        self.auth_api = None
        self.groups_api = None
        self.users_api = None
        self.worlds_api = None
        self.current_user = None
        self.is_logged_in = False
        self.is_inviting = False
        self.invite_thread = None
        self.config_manager = config_manager
        self.plugin_manager = plugin_manager
        
        # Callbacks
        self.on_login_status_change = None
        self.on_invite_progress = None
        self.on_log_message = None
        self.on_log_watcher_status_change = None
        
        # Initialize log watcher
        self.log_watcher = VRChatLogWatcher(self)
        self._player_join_times = {}
        
    def set_gui_callbacks(self, 
                     update_login_status: Callable[[bool, str], None] = None,
                     update_invite_progress: Callable[[int, int, str], None] = None,
                     add_log_message: Callable[[str], None] = None,
                     update_log_watcher_status: Callable[[], None] = None):
        """Set GUI callbacks"""
        self.on_login_status_change = update_login_status
        self.on_invite_progress = update_invite_progress
        self.on_log_message = add_log_message
        self.on_log_watcher_status_change = update_log_watcher_status
        
        # Don't start log watching automatically anymore
        # self.start_log_watching()
        
    def log(self, message: str):
        """Log a message"""
        logger.info(message)
        if self.on_log_message:
            self.on_log_message(message)
            
    def login(self, username: str, password: str, get_2fa_code_callback=None, login_result_callback=None, save_credentials=False):
        """Login to VRChat API"""
        if not username or not password:
            self.log("Username and password are required")
            if login_result_callback:
                login_result_callback(False, "Username and password are required")
            return False

        # Create configuration
        configuration = vrchatapi.Configuration(
            username=username,
            password=password,
        )
        
        try:
            # Create API client
            self.api_client = vrchatapi.ApiClient(configuration)
            self.api_client.user_agent = "VRChatAutoInvite/1.0.0"
            
            # Initialize API instances
            self.auth_api = authentication_api.AuthenticationApi(self.api_client)
            self.groups_api = groups_api.GroupsApi(self.api_client)
            self.users_api = users_api.UsersApi(self.api_client)
            self.worlds_api = worlds_api.WorldsApi(self.api_client)
            
            # Try to get current user
            try:
                self.current_user = self.auth_api.get_current_user()
                self.is_logged_in = True
                status_message = f"Logged in as: {self.current_user.display_name}"
                self.log(f"Successfully {status_message}")
                
                # Save credentials if requested and config manager exists
                if save_credentials and self.config_manager:
                    self.log("Saving login credentials for future sessions...")
                    saved = self.config_manager.save_credentials(username, password)
                    if saved:
                        self.log("Login credentials saved successfully")
                    else:
                        self.log("Failed to save login credentials")
                    
                    # Save auth cookies for faster login next time
                    if hasattr(self.api_client, 'cookie'):
                        auth_cookie = self.api_client.cookie
                        saved = self.config_manager.save_auth_token(auth_cookie)
                        if saved:
                            self.log("Authentication token saved successfully")
                        else:
                            self.log("Failed to save authentication token")
                
                if login_result_callback:
                    login_result_callback(True, status_message)
                
                # Update login status
                if self.on_login_status_change:
                    self.on_login_status_change(True, status_message)
                    
                return True
            except ApiException as e:
                error_message = str(e)
                error_body = e.body if hasattr(e, 'body') else ""
                
                self.log(f"API Exception: {error_message}")
                self.log(f"Response body: {error_body}")
                
                # Check for 2FA requirement
                requires_2fa = False
                is_email_2fa = False
                
                if "requiresTwoFactorAuth" in error_body:
                    requires_2fa = True
                    is_email_2fa = "emailOtp" in error_body
                elif "requires two-factor authentication" in error_message.lower():
                    requires_2fa = True
                    is_email_2fa = "email" in error_message.lower()
                
                if requires_2fa:
                    auth_type = "Email" if is_email_2fa else "Authenticator"
                    self.log(f"2FA required ({auth_type})")
                    
                    if get_2fa_code_callback:
                        code = get_2fa_code_callback(is_email_2fa)
                        self.log(f"2FA code received: {'Yes' if code else 'No/Cancelled'}")
                        
                        if code:
                            try:
                                if is_email_2fa:
                                    self.log("Verifying email 2FA code...")
                                    self.auth_api.verify2_fa_email_code(two_factor_email_code=TwoFactorEmailCode(code=code))
                                else:
                                    self.log("Verifying authenticator 2FA code...")
                                    self.auth_api.verify2_fa(two_factor_auth_code=TwoFactorAuthCode(code=code))
                                
                                self.current_user = self.auth_api.get_current_user()
                                self.is_logged_in = True
                                status_message = f"Logged in as: {self.current_user.display_name}"
                                self.log(f"Successfully {status_message}")
                                if login_result_callback:
                                    login_result_callback(True, status_message)
                                return True
                            except ApiException as e2:
                                error_message = f"2FA verification failed: {str(e2)}"
                                self.log(error_message)
                                if login_result_callback:
                                    login_result_callback(False, error_message)
                                return False
                        else:
                            error_message = "2FA code required but not provided or cancelled"
                            self.log(error_message)
                            if login_result_callback:
                                login_result_callback(False, error_message)
                            return False
                    else:
                        error_message = "2FA required but no callback provided"
                        self.log(error_message)
                        if login_result_callback:
                            login_result_callback(False, error_message)
                        return False
                else:
                    self.log(f"Login failed: {error_message}")
                    if login_result_callback:
                        login_result_callback(False, f"Login failed: {error_message}")
                    return False
        except Exception as e:
            error_message = f"Login failed: {str(e)}"
            self.log(error_message)
            if login_result_callback:
                login_result_callback(False, error_message)
            return False
    
    def get_group_members(self, group_id):
        """Get all members of a group"""
        if not self.is_logged_in:
            self.log("You must be logged in first")
            return []
            
        try:
            # Get group members
            members = []
            offset = 0
            limit = 100  # API usually limits results per page
            
            while True:
                # Get a page of members
                page = self.groups_api.get_group_members(group_id, n=limit, offset=offset)
                
                if not page or not hasattr(page, 'users') or not page.users:
                    break
                    
                members.extend(page.users)
                
                # If we got fewer results than the limit, we've reached the end
                if len(page.users) < limit:
                    break
                    
                # Move to the next page
                offset += limit
                
            self.log(f"Found {len(members)} members in group {group_id}")
            return members
            
        except ApiException as e:
            self.log(f"Failed to get group members: {str(e)}")
            return []

    def get_current_instance(self):
        """Get the current VRChat instance ID the user is in"""
        if not self.is_logged_in:
            self.log("You must be logged in first")
            return None
            
        try:
            # Get the current user's information to find their location
            current_user = self.users_api.get_user(self.current_user.id)
            
            if not current_user or not hasattr(current_user, 'location') or not current_user.location:
                self.log("User is not in any instance")
                return None
                
            # The location format is typically worldId:instanceId
            location = current_user.location
            if ':' not in location:
                self.log(f"Invalid location format: {location}")
                return None
                
            # Extract the instance ID from the location
            instance_id = location.split(':', 1)[1]
            self.log(f"Current instance ID: {instance_id}")
            return instance_id
            
        except Exception as e:
            self.log(f"Error getting current instance: {str(e)}")
            return None

    def is_instance_from_group(self, instance_id, group_id):
        """Check if the given instance belongs to the specified group
        
        VRChat group instance IDs typically follow these formats:
        - Group public instance: grp_[groupID]
        - Group private instance: grp_[groupID]~region(...)~nonce(...)
        """
        if not instance_id or not group_id:
            return False
            
        # Check if it's a group instance
        if not instance_id.startswith('grp_'):
            self.log(f"Instance {instance_id} is not a group instance")
            return False
            
        # Extract the group ID from the instance ID
        # Group instance format: grp_[groupID] or grp_[groupID]~region(...)~nonce(...)
        instance_group_id = instance_id.split('~')[0].replace('grp_', '')
        
        # Compare with the target group ID
        is_match = instance_group_id == group_id
        if is_match:
            self.log(f"Instance {instance_id} belongs to group {group_id}")
        else:
            self.log(f"Instance {instance_id} belongs to group {instance_group_id}, not {group_id}")
            
        return is_match

    def invite_instance_players_to_group(self, group_id, max_threads=5, delay=5):
        """Invite players from current instance to a group if they're not already members and have been in the instance long enough"""
        if not self.is_logged_in:
            self.log("You must be logged in first")
            return False
        if not group_id:
            self.log("Group ID is required")
            return False
        
        # Check if VRChat is running
        if not self.is_vrchat_running():
            error_message = "VRChat does not appear to be running. Please start VRChat before sending invites."
            self.log(error_message)
            return False
            
        # Check if the current user is a member of the group
        if not self.is_current_user_in_group(group_id):
            error_message = f"You are not a member of group {group_id}. You can only invite players to groups you are a member of."
            self.log(error_message)
            return False
        
        # We no longer need to start the log watcher here as it's handled by the GUI
        # Just check if it's running and log a message if not
        if not self.is_log_watching():
            self.log("Log watcher is not running. Using one-time log scan for player detection.")
        
        # Get current instance
        instance_id = self.get_current_instance()
        if not instance_id:
            self.log("Could not determine current instance")
            return False
            
        # Check if the current instance belongs to the specified group
        if not self.is_instance_from_group(instance_id, group_id):
            error_message = f"You are not in a group instance for group {group_id}. You can only invite players when you are in an instance of the group you're inviting to."
            self.log(error_message)
            return False
        
        # Get players in instance with their join times
        players_with_times = self.get_players_in_instance_with_times(instance_id)
        if not players_with_times:
            self.log("No players found in the instance")
            return False
        
        # Get group members
        self.log(f"Getting members of group {group_id}...")
        group_members = self.get_group_members(group_id)
        member_ids = [member.id for member in group_members] if group_members else []
        
        # Get pending invites for the group
        self.log(f"Getting pending invites for group {group_id}...")
        pending_invites = []
        try:
            # Try to get pending invites for the group
            pending_invites_response = self.groups_api.get_group_invites(group_id)
            if pending_invites_response and hasattr(pending_invites_response, 'data'):
                pending_invites = [invite.user_id for invite in pending_invites_response.data]
                self.log(f"Found {len(pending_invites)} pending invites for group {group_id}")
        except Exception as e:
            self.log(f"Error getting pending invites: {str(e)}")
            self.log("Will continue without checking pending invites")
        
        # Get current time
        current_time = datetime.now()
        
        # Log all players found in the instance
        self.log(f"Processing {len(players_with_times)} players found in instance {instance_id}:")
        for player, join_time in players_with_times:
            status = []
            
            if player.id == self.current_user.id:
                status.append("This is you")
            if player.id in member_ids:
                status.append("Already in group")
            if player.id in pending_invites:
                status.append("Has pending invite")
            
            time_in_instance = (current_time - join_time).total_seconds()
            if time_in_instance < delay:
                status.append(f"Needs to wait {delay - time_in_instance:.1f} more seconds")
                
            status_str = f" ({', '.join(status)})" if status else ""
            self.log(f"  - {player.display_name} ({player.id}): in instance for {time_in_instance:.1f} seconds{status_str}")
        
        # Filter out yourself, existing group members, players with pending invites, and players who haven't been in the instance long enough
        filtered_players = []
        for player, join_time in players_with_times:
            if player.id == self.current_user.id:
                continue  # Skip yourself
            
            if player.id in member_ids:
                continue  # Skip existing group members
            
            if player.id in pending_invites:
                continue  # Skip players with pending invites
            
            # Check if player has been in the instance long enough
            time_in_instance = (current_time - join_time).total_seconds()
            if time_in_instance < delay:
                continue  # Skip players who haven't been in the instance long enough
            
            filtered_players.append(player)
        
        if not filtered_players:
            self.log("No eligible players to invite")
            return False
        
        # Start invitation process with threading
        self.log(f"Starting invitation process for {len(filtered_players)} eligible players:")
        for player in filtered_players:
            self.log(f"  - Will invite: {player.display_name} ({player.id})")
            
        self.is_inviting = True
        
        # Run the invitation process in a separate thread
        self.invite_thread = threading.Thread(
            target=self._invite_thread_pool,
            args=(group_id, filtered_players, max_threads, delay),
            daemon=True
        )
        self.invite_thread.start()
        
        return True

    def get_players_in_instance(self, instance_id):
        """Get players in the specified VRChat instance using the log watcher"""
        if not self.is_logged_in:
            self.log("You must be logged in first")
            return []
            
        try:
            # Check if log watcher is running
            if not self.is_log_watching():
                self.log("Log watcher is not running. Using one-time log scan instead.")
                # Use the fallback method to parse logs directly
                log_path = self._get_vrchat_log_path()
                if not log_path:
                    self.log("Could not find VRChat log file")
                    return []
                return self._parse_vrchat_logs_for_players(log_path, instance_id)
            
            # Get active players from the log watcher
            active_players, _ = self.log_watcher.get_active_players()
            
            if not active_players:
                self.log("No active players found in the current instance")
            else:
                self.log(f"Found {len(active_players)} active players in the current instance")
                for player in active_players:
                    time_in_instance = "unknown"
                    if player.id in self._player_join_times:
                        join_time = self._player_join_times[player.id]
                        time_in_instance = f"{(datetime.now() - join_time).total_seconds():.1f} seconds"
                    self.log(f"  - {player.display_name} ({player.id}): in instance for {time_in_instance}")
            
            return active_players
            
        except Exception as e:
            self.log(f"Error getting players from log watcher: {str(e)}")
            self.log(f"Exception details: {traceback.format_exc()}")
            return []

    def get_players_in_instance_with_times(self, instance_id):
        """Get players in the instance along with their join times using the log watcher"""
        try:
            # Get players from the instance using the log watcher
            self.log(f"Getting players and join times for instance {instance_id}")
            players = self.get_players_in_instance(instance_id)
            
            if not players:
                self.log("No players found in the instance logs")
                return []
            
            # Use the join times collected by the log watcher
            current_time = datetime.now()
            players_with_times = []
            
            self.log(f"Processing join times for {len(players)} players:")
            for player in players:
                # Get the join time from our stored dictionary
                if player.id in self._player_join_times:
                    join_time = self._player_join_times[player.id]
                    time_in_instance = (current_time - join_time).total_seconds()
                    players_with_times.append((player, join_time))
                    self.log(f"  - {player.display_name} ({player.id}): joined at {join_time.strftime('%Y-%m-%d %H:%M:%S')}, in instance for {time_in_instance:.1f} seconds")
                else:
                    # If we don't have a join time (shouldn't happen), use current time
                    self.log(f"  - {player.display_name} ({player.id}): No join time found, using current time")
                    players_with_times.append((player, current_time))
            
            return players_with_times
            
        except Exception as e:
            self.log(f"Error getting players with times: {str(e)}")
            return []

    def _invite_thread_pool(self, group_id, players, max_threads, delay):
        """Invite multiple players to a group using a thread pool"""
        total_players = len(players)
        invited_count = 0
        failed_count = 0
        skipped_count = 0
        
        self.log(f"Starting invitation thread pool for {total_players} players to group {group_id}")
        
        if self.on_invite_progress:
            self.on_invite_progress(invited_count, total_players, "Starting invitations...")
        
        # Create a thread-safe queue for players
        player_queue = Queue()
        for player in players:
            player_queue.put(player)
        
        # Create a lock for thread-safe operations
        lock = threading.Lock()
        
        # Create a function for worker threads
        def worker():
            nonlocal invited_count, failed_count, skipped_count
            while not player_queue.empty() and self.is_inviting:
                try:
                    # Check stop flag before getting next player
                    if not self.is_inviting:
                        break
                    
                    player = player_queue.get(block=False)
                    self.log(f"Processing player: {player.display_name} ({player.id})")
                    
                    # Check stop flag again before processing
                    if not self.is_inviting:
                        # Put the player back in the queue
                        player_queue.put(player)
                        break
                    
                    try:
                        # Double-check if player is already in the group or has a pending invite
                        should_invite = True
                        
                        # Check if player is already in the group
                        try:
                            self.log(f"Checking if {player.display_name} is already in group {group_id}...")
                            # Try to get the player's membership status
                            membership = self.groups_api.get_group_member(group_id, player.id)
                            if membership:
                                with lock:
                                    skipped_count += 1
                                    status_message = f"Skipped {player.display_name} - already in group ({invited_count}/{total_players})"
                                    self.log(status_message)
                                    if self.on_invite_progress:
                                        self.on_invite_progress(invited_count, total_players, status_message)
                                should_invite = False
                        except ApiException as e:
                            # 404 means the player is not in the group, which is what we want
                            if e.status != 404:
                                self.log(f"Error checking membership for {player.display_name}: {str(e)}")
                            else:
                                self.log(f"{player.display_name} is not in group {group_id} (404 response, which is expected)")
                        
                        # Check if player already has a pending invite
                        if should_invite:
                            try:
                                self.log(f"Checking if {player.display_name} already has a pending invite to group {group_id}...")
                                # Try to get pending invites for the group
                                pending_invites_response = self.groups_api.get_group_invites(group_id)
                                if pending_invites_response and hasattr(pending_invites_response, 'data'):
                                    pending_invites = [invite.user_id for invite in pending_invites_response.data]
                                    if player.id in pending_invites:
                                        with lock:
                                            skipped_count += 1
                                            status_message = f"Skipped {player.display_name} - already has pending invite ({invited_count}/{total_players})"
                                            self.log(status_message)
                                            if self.on_invite_progress:
                                                self.on_invite_progress(invited_count, total_players, status_message)
                                        should_invite = False
                                    else:
                                        self.log(f"{player.display_name} does not have a pending invite to group {group_id}")
                            except ApiException as e:
                                self.log(f"Error checking pending invites for {player.display_name}: {str(e)}")
                        
                        # Send group invite if all checks pass
                        if should_invite:
                            self.log(f"Sending invite to {player.display_name} ({player.id}) for group {group_id}...")
                            try:
                                # Create the proper request object for the group invite
                                invite_request = CreateGroupInviteRequest(user_id=player.id)
                                
                                # Send the invite with the proper request object
                                invite_response = self.groups_api.create_group_invite(
                                    group_id=group_id,
                                    create_group_invite_request=invite_request
                                )
                                
                                self.log(f"Invite API response: {invite_response}")
                                with lock:
                                    invited_count += 1
                                    status_message = f"Invited {player.display_name} ({invited_count}/{total_players})"
                                    self.log(status_message)
                                    if self.on_invite_progress:
                                        self.on_invite_progress(invited_count, total_players, status_message)
                            except ApiException as e:
                                self.log(f"API Exception when inviting {player.display_name}: {str(e)}")
                                with lock:
                                    failed_count += 1
                                    error_message = f"Failed to invite {player.display_name}: {str(e)}"
                                    self.log(error_message)
                                    # Log more details about the API exception
                                    if hasattr(e, 'status'):
                                        self.log(f"API Exception details - Status: {e.status}, Reason: {e.reason}")
                                    if hasattr(e, 'body') and e.body:
                                        self.log(f"Response body: {e.body}")
                            except Exception as e:
                                self.log(f"Unexpected error inviting {player.display_name}: {str(e)}")
                                with lock:
                                    failed_count += 1
                                    error_message = f"Failed to invite {player.display_name}: {str(e)}"
                                    self.log(error_message)
                                    self.log(f"Exception details: {traceback.format_exc()}")
                    
                    except ApiException as e:
                        with lock:
                            failed_count += 1
                            error_message = f"Failed to invite {player.display_name}: {str(e)}"
                            self.log(error_message)
                            # Log more details about the API exception
                            self.log(f"API Exception details - Status: {e.status}, Reason: {e.reason}")
                            if hasattr(e, 'body') and e.body:
                                self.log(f"Response body: {e.body}")
                    except Exception as e:
                        with lock:
                            failed_count += 1
                            error_message = f"Unexpected error inviting {player.display_name}: {str(e)}"
                            self.log(error_message)
                            self.log(f"Exception details: {traceback.format_exc()}")
                    
                    # Check stop flag before waiting
                    if not self.is_inviting:
                        break
                    
                    # Wait for the specified delay before next invitation (per thread)
                    self.log(f"Waiting {delay} seconds before processing next player...")
                    time.sleep(delay)
                except Exception as e:
                    # Queue is empty or other error
                    self.log(f"Worker thread error: {str(e)}")
                    self.log(f"Exception details: {traceback.format_exc()}")
                    break
        
        # Create and start worker threads
        threads = []
        for i in range(min(max_threads, total_players)):
            self.log(f"Starting worker thread {i+1}/{min(max_threads, total_players)}")
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete or until stopped
        for i, thread in enumerate(threads):
            self.log(f"Waiting for worker thread {i+1}/{len(threads)} to complete...")
            thread.join()
            self.log(f"Worker thread {i+1}/{len(threads)} completed")
        
        # Update status based on whether process was stopped or completed
        if not self.is_inviting:
            completion_message = f"Invitation process stopped. Invited {invited_count}/{total_players} players. Failed: {failed_count}, Skipped: {skipped_count}"
        else:
            completion_message = f"Invitation process completed. Invited {invited_count}/{total_players} players. Failed: {failed_count}, Skipped: {skipped_count}"
        
        self.is_inviting = False
        self.log(completion_message)
        if self.on_invite_progress:
            self.on_invite_progress(invited_count, total_players, completion_message)
            
    def get_plugin_names(self):
        """Get list of plugin names"""
        if self.plugin_manager:
            return self.plugin_manager.get_plugin_names()
        return []
        
    def get_plugin_info(self, name):
        """Get information about a specific plugin"""
        return self.plugin_manager.get_plugin_info(name) if self.plugin_manager else None
        
    def load_plugin_from_file(self, file_path):
        """Load a plugin from a file"""
        return self.plugin_manager.load_plugin_from_file(file_path) if self.plugin_manager else None
        
    def refresh_plugins(self):
        """Refresh the list of available plugins"""
        return self.plugin_manager.refresh_plugins() if self.plugin_manager else None

    # Add methods to handle log watcher events
    def on_instance_change(self, instance_id):
        """Called when the instance changes"""
        self.log(f"Current instance changed to: {instance_id}")
        # You could trigger other actions here when the instance changes
        
    def on_player_join(self, player_id, player_name, timestamp):
        """Called when a player joins the instance"""
        # Update the player join times
        self._player_join_times[player_id] = timestamp
        
    def on_player_leave(self, player_id, player_name, timestamp):
        """Called when a player leaves the instance"""
        # Remove from join times if they've left
        if player_id in self._player_join_times:
            del self._player_join_times[player_id]
            
    def start_log_watching(self, scan_existing=True):
        """Start watching VRChat logs for player events"""
        try:
            if not hasattr(self, 'log_watcher') or not self.log_watcher:
                self.log_watcher = VRChatLogWatcher(self.log)
                
            if hasattr(self.log_watcher, 'is_watching') and self.log_watcher.is_watching:
                self.log("Log watcher is already running")
                return True
                
            log_path = self._get_vrchat_log_path()
            if not log_path:
                self.log("Could not find VRChat log file")
                return False
                
            success = self.log_watcher.start_watching(log_path, scan_existing)
            
            # Notify GUI of status change
            if self.on_log_watcher_status_change:
                self.on_log_watcher_status_change()
                
            return success
        except Exception as e:
            self.log(f"Error starting log watcher: {str(e)}")
            self.log(f"Exception details: {traceback.format_exc()}")
            return False
            
    def stop_log_watching(self):
        """Stop watching VRChat logs"""
        try:
            if not hasattr(self, 'log_watcher') or not self.log_watcher:
                self.log("Log watcher is not initialized")
                return False
                
            if not hasattr(self.log_watcher, 'is_watching') or not self.log_watcher.is_watching:
                self.log("Log watcher is not running")
                return True
                
            self.log_watcher.stop_watching()
            
            # Notify GUI of status change
            if self.on_log_watcher_status_change:
                self.on_log_watcher_status_change()
                
            return True
        except Exception as e:
            self.log(f"Error stopping log watcher: {str(e)}")
            self.log(f"Exception details: {traceback.format_exc()}")
            return False
        
    def is_log_watching(self):
        """Check if the log watcher is currently running"""
        return hasattr(self.log_watcher, 'is_watching') and self.log_watcher.is_watching
        
    def _get_vrchat_log_path(self):
        """Get the path to the latest VRChat log file"""
        try:
            # Default VRChat log directory paths
            possible_paths = [
                os.path.expanduser("~\\AppData\\LocalLow\\VRChat\\VRChat"),  # Windows
                os.path.expanduser("~/Library/Logs/VRChat/VRChat"),          # macOS
                os.path.expanduser("~/.config/unity3d/VRChat/VRChat")        # Linux
            ]
            
            log_dir = None
            for path in possible_paths:
                if os.path.exists(path):
                    log_dir = path
                    self.log(f"Found VRChat log directory: {path}")
                    break
                    
            if not log_dir:
                self.log("Could not find VRChat log directory. Checked paths:")
                for path in possible_paths:
                    self.log(f"  - {path}")
                return None
                
            # Find all log files (usually named output_log_*.txt)
            log_files = [f for f in os.listdir(log_dir) if f.startswith("output_log_") and f.endswith(".txt")]
            if not log_files:
                self.log("No VRChat log files found in directory")
                return None
                
            # Log information about available log files
            self.log(f"Found {len(log_files)} VRChat log files:")
            
            # Get file info for sorting
            log_file_info = []
            for f in log_files:
                full_path = os.path.join(log_dir, f)
                mod_time = os.path.getmtime(full_path)
                size = os.path.getsize(full_path)
                log_file_info.append((f, full_path, mod_time, size))
            
            # Sort by modification time (newest first)
            log_file_info.sort(key=lambda x: x[2], reverse=True)
            
            # Display info about the top 5 most recent log files
            for i, (filename, path, mod_time, size) in enumerate(log_file_info[:5]):
                mod_time_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
                size_kb = size / 1024
                self.log(f"  {i+1}. {filename} - Last modified: {mod_time_str}, Size: {size_kb:.2f} KB")
            
            # Use the most recent log file
            latest_log_file = log_file_info[0][1]
            self.log(f"Using most recent log file: {latest_log_file}")
            
            # Check if the log file was modified recently (within the last hour)
            latest_mod_time = log_file_info[0][2]
            time_diff = time.time() - latest_mod_time
            if time_diff > 3600:  # More than an hour old
                self.log(f"WARNING: Latest log file is {time_diff/60:.1f} minutes old. VRChat may not be running or logs may not be updating.")
            else:
                self.log(f"Log file is current (last modified {time_diff:.1f} seconds ago)")
                
            return latest_log_file
            
        except Exception as e:
            self.log(f"Error finding VRChat log file: {str(e)}")
            return None
            
    def cleanup(self):
        """Clean up resources when the application is closing"""
        self.log("Cleaning up resources...")
        
        # Stop any ongoing invitation process
        if self.is_inviting:
            self.stop_inviting()
            
        # Stop log watching
        self.stop_log_watching()
        
        self.log("Cleanup complete")

    def _parse_vrchat_logs_for_players(self, log_path, instance_id):
        """Parse VRChat logs to find players in the specified instance by scanning for join/leave events (fallback method)"""
        try:
            self.log(f"Parsing log file: {log_path}")
            
            # Get file modification time to show how recent the log is
            mod_time = datetime.fromtimestamp(os.path.getmtime(log_path))
            self.log(f"Log file last modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Track all player join and leave events
            player_events = {}  # Dictionary to track player events by ID
            current_instance = None
            instance_change_time = None
            
            # First pass: scan the entire log file to find the current instance
            self.log("Scanning log file for instance information...")
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Look for instance change events - try different possible formats
                    if "Joining" in line and "Room" in line:
                        timestamp_match = re.search(r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})', line)
                        
                        # Try different patterns for instance ID
                        instance_patterns = [
                            r'Joining or Creating Room:\s+(\S+)',  # Format: Joining or Creating Room: wrld_123
                            r'Joining Room:\s+(\S+)',              # Format: Joining Room: wrld_123
                            r'Room:\s+(\S+)',                      # Format: Room: wrld_123
                            r'Joining\s+(\S+)'                     # Format: Joining wrld_123
                        ]
                        
                        instance_id_found = None
                        for pattern in instance_patterns:
                            instance_match = re.search(pattern, line)
                            if instance_match:
                                instance_id_found = instance_match.group(1).strip()
                                break
                        
                        if timestamp_match and instance_id_found:
                            timestamp_str = timestamp_match.group(1)
                            current_instance = instance_id_found
                            instance_change_time = datetime.strptime(timestamp_str, '%Y.%m.%d %H:%M:%S')
                            self.log(f"Found instance change at {timestamp_str}: {current_instance}")
            
            if not current_instance:
                self.log("Could not find current instance in logs")
                return []
                
            self.log(f"Current instance from logs: {current_instance}")
            
            # If instance_id was provided, check if it matches
            if instance_id and instance_id != current_instance:
                self.log(f"Warning: Provided instance ID ({instance_id}) doesn't match instance found in logs ({current_instance})")
                self.log(f"Using instance from logs: {current_instance}")
            
            # Use the instance from logs if none was provided
            if not instance_id:
                instance_id = current_instance
                
            # Second pass: scan for all player join and leave events
            self.log(f"Scanning log file for player join/leave events in instance {instance_id}...")
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Extract timestamp from the line
                    timestamp_match = re.search(r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})', line)
                    if not timestamp_match:
                        continue
                        
                    timestamp_str = timestamp_match.group(1)
                    timestamp = datetime.strptime(timestamp_str, '%Y.%m.%d %H:%M:%S')
                    
                    # Skip events before the instance change
                    if instance_change_time and timestamp < instance_change_time:
                        continue
                    
                    # Look for player join events
                    if "[Behaviour] OnPlayerJoined" in line:
                        player_match = re.search(r'OnPlayerJoined\s+(\S+)\s+\((\S+)\)', line)
                        if player_match:
                            player_name = player_match.group(1).strip()
                            player_id = player_match.group(2).strip()
                            
                            # Record the join event
                            if player_id not in player_events:
                                player_events[player_id] = {
                                    'name': player_name,
                                    'joins': [],
                                    'leaves': []
                                }
                            
                            player_events[player_id]['joins'].append(timestamp)
                            self.log(f"Found player join: {player_name} ({player_id}) at {timestamp_str}")
                    
                    # Look for player leave events
                    elif "[Behaviour] OnPlayerLeft" in line:
                        player_match = re.search(r'OnPlayerLeft\s+(\S+)\s+\((\S+)\)', line)
                        if player_match:
                            player_name = player_match.group(1).strip()
                            player_id = player_match.group(2).strip()
                            
                            # Record the leave event
                            if player_id not in player_events:
                                player_events[player_id] = {
                                    'name': player_name,
                                    'joins': [],
                                    'leaves': []
                                }
                            
                            player_events[player_id]['leaves'].append(timestamp)
                            self.log(f"Found player leave: {player_name} ({player_id}) at {timestamp_str}")
            
            # Determine which players are still in the instance
            active_players = []
            player_join_times = {}
            
            for player_id, events in player_events.items():
                # If there are more joins than leaves, the player is still in the instance
                if len(events['joins']) > len(events['leaves']):
                    # Use the most recent join time
                    latest_join = max(events['joins'])
                    
                    # Create player object
                    player = SimpleNamespace(
                        id=player_id,
                        display_name=events['name']
                    )
                    
                    active_players.append(player)
                    player_join_times[player_id] = latest_join
                    
                    time_in_instance = (datetime.now() - latest_join).total_seconds()
                    self.log(f"Active player: {events['name']} ({player_id}), in instance for {time_in_instance:.1f} seconds")
            
            # Log summary
            if active_players:
                self.log(f"Found {len(active_players)} active players in instance {instance_id}")
            else:
                self.log(f"No active players found in instance {instance_id}")
            
            # Store join times for later use
            self._player_join_times = {player_id: player_join_times[player_id] for player_id in player_join_times}
            return active_players
            
        except Exception as e:
            self.log(f"Error parsing VRChat logs: {str(e)}")
            self.log(f"Exception details: {traceback.format_exc()}")
            return []

    def stop_inviting(self):
        """Stop the invitation process"""
        if not hasattr(self, 'is_inviting') or not self.is_inviting:
            self.log("No invitation process is running")
            return False
        
        self.log("Stopping invitation process...")
        self.is_inviting = False
        
        # Wait for the invitation thread to finish
        if hasattr(self, 'invite_thread') and self.invite_thread and self.invite_thread.is_alive():
            self.log("Waiting for invitation thread to finish...")
            self.invite_thread.join(timeout=1.0)  # Wait up to 1 second for thread to finish
        
        return True

    def auto_login(self, login_result_callback=None):
        """Attempt to login using saved credentials"""
        if not self.config_manager:
            self.log("No config manager available, cannot auto-login")
            if login_result_callback:
                login_result_callback(False, "No config manager available")
            return False
            
        # First try to login with saved auth token (faster)
        auth_token = self.config_manager.get_auth_token()
        if auth_token:
            self.log("Attempting to login with saved authentication token...")
            try:
                # Create a configuration without username/password
                configuration = vrchatapi.Configuration()
                
                # Create API client
                self.api_client = vrchatapi.ApiClient(configuration)
                self.api_client.user_agent = "VRChatAutoInvite/1.0.0"
                
                # Set the auth cookie directly
                self.api_client.cookie = auth_token
                
                # Initialize API instances
                self.auth_api = authentication_api.AuthenticationApi(self.api_client)
                self.groups_api = groups_api.GroupsApi(self.api_client)
                self.users_api = users_api.UsersApi(self.api_client)
                self.worlds_api = worlds_api.WorldsApi(self.api_client)
                
                # Try to get current user to verify the token is valid
                self.current_user = self.auth_api.get_current_user()
                self.is_logged_in = True
                status_message = f"Logged in as: {self.current_user.display_name}"
                self.log(f"Successfully {status_message}")
                
                if login_result_callback:
                    login_result_callback(True, status_message)
                return True
            except Exception as e:
                self.log(f"Auto-login with token failed: {str(e)}")
                # Token might be expired, continue to try with username/password
        
        # If token login failed, try with saved username/password
        username, password = self.config_manager.get_credentials()
        if username and password:
            self.log("Attempting to login with saved credentials...")
            return self.login(username, password, None, login_result_callback, False)
        else:
            self.log("No saved credentials found")
            if login_result_callback:
                login_result_callback(False, "No saved credentials found")
            return False

    def logout(self, clear_saved_credentials=False):
        """Logout from VRChat API"""
        if not self.is_logged_in:
            self.log("Not logged in")
            return
            
        try:
            if self.auth_api:
                # Call logout endpoint
                self.auth_api.logout()
                
            # Clear saved credentials if requested
            if clear_saved_credentials and self.config_manager:
                self.config_manager.clear_saved_login()
                self.log("Cleared saved login information")
                
        except Exception as e:
            self.log(f"Error during logout: {str(e)}")
        finally:
            # Reset client state
            self.api_client = None
            self.auth_api = None
            self.groups_api = None
            self.users_api = None
            self.worlds_api = None
            self.current_user = None
            self.is_logged_in = False
            
            self.log("Logged out successfully")
            
            # Update UI if callback is set
            if self.on_login_status_change:
                self.on_login_status_change(False, "Logged out")

    def is_vrchat_running(self):
        """Check if VRChat is currently running by looking at log file modification time"""
        try:
            log_path = self._get_vrchat_log_path()
            if not log_path or not os.path.exists(log_path):
                self.log("Could not find VRChat log file - VRChat may not be running")
                return False
                
            # Check if the log file was modified recently (within the last 5 minutes)
            mod_time = os.path.getmtime(log_path)
            time_diff = time.time() - mod_time
            
            # If log file was modified in the last 5 minutes, VRChat is likely running
            if time_diff <= 300:  # 5 minutes in seconds
                self.log(f"VRChat appears to be running (log updated {time_diff:.1f} seconds ago)")
                return True
            else:
                self.log(f"VRChat may not be running (log last updated {time_diff/60:.1f} minutes ago)")
                return False
                
        except Exception as e:
            self.log(f"Error checking if VRChat is running: {str(e)}")
            return False

    def is_current_user_in_group(self, group_id):
        """Check if the current logged-in user is a member of the specified group"""
        if not self.is_logged_in or not self.current_user:
            self.log("You must be logged in first")
            return False
            
        try:
            # Try to get the user's membership status in the group
            self.log(f"Checking if current user ({self.current_user.display_name}) is a member of group {group_id}...")
            
            try:
                # This will throw a 404 exception if the user is not in the group
                membership = self.groups_api.get_group_member(group_id, self.current_user.id)
                if membership:
                    self.log(f"Current user is a member of group {group_id}")
                    return True
            except ApiException as e:
                # 404 means the user is not in the group
                if e.status == 404:
                    self.log(f"Current user is NOT a member of group {group_id}")
                    return False
                else:
                    # Some other API error
                    self.log(f"Error checking group membership: {str(e)}")
                    if hasattr(e, 'status'):
                        self.log(f"API Exception details - Status: {e.status}, Reason: {e.reason}")
                    if hasattr(e, 'body') and e.body:
                        self.log(f"Response body: {e.body}")
                    return False
                    
        except Exception as e:
            self.log(f"Unexpected error checking group membership: {str(e)}")
            return False
            
        return False

    def invite_players(self, group_id, players, delay_seconds=2.0, max_workers=1):
        """Invite players to a group"""
        if not self.is_logged_in:
            self.log("You must be logged in first")
            return False
            
        # Check if VRChat is running
        if not self.is_vrchat_running():
            error_message = "VRChat does not appear to be running. Please start VRChat before sending invites."
            self.log(error_message)
            if self.on_invite_progress:
                self.on_invite_progress(0, len(players), error_message)
            return False
            
        # Check if the current user is a member of the group
        if not self.is_current_user_in_group(group_id):
            error_message = f"You are not a member of group {group_id}. You can only invite players to groups you are a member of."
            self.log(error_message)
            if self.on_invite_progress:
                self.on_invite_progress(0, len(players), error_message)
            return False
            
        # Get current instance
        instance_id = self.get_current_instance()
        if not instance_id:
            error_message = "Could not determine current instance"
            self.log(error_message)
            if self.on_invite_progress:
                self.on_invite_progress(0, len(players), error_message)
            return False
            
        # Check if the current instance belongs to the specified group
        if not self.is_instance_from_group(instance_id, group_id):
            error_message = f"You are not in a group instance for group {group_id}. You can only invite players when you are in an instance of the group you're inviting to."
            self.log(error_message)
            if self.on_invite_progress:
                self.on_invite_progress(0, len(players), error_message)
            return False
            
        if self.is_inviting:
            self.log("Already inviting players, please wait or stop the current process")
            return False
            
        # Start invitation process in a separate thread
        self.is_inviting = True
        self.invite_thread = threading.Thread(
            target=self._invite_players_thread,
            args=(group_id, players, delay_seconds, max_workers),
            daemon=True
        )
        self.invite_thread.start()
        return True

    def _invite_players_thread(self, group_id, players, delay_seconds, max_workers):
        """Thread function to invite players to a group"""
        try:
            # Create a queue of players to invite
            player_queue = Queue()
            for player in players:
                player_queue.put(player)
                
            total_players = len(players)
            invited_count = 0
            failed_count = 0
            skipped_count = 0
            
            self.log(f"Starting to invite {total_players} players to group {group_id}")
            if self.on_invite_progress:
                self.on_invite_progress(invited_count, total_players, f"Starting to invite {total_players} players...")
                
            # Use a lock for thread safety when updating counters
            lock = threading.Lock()
            
            while not player_queue.empty() and self.is_inviting:
                # Check if VRChat is still running periodically
                if invited_count % 5 == 0:  # Check every 5 invites
                    if not self.is_vrchat_running():
                        error_message = "VRChat appears to have closed. Stopping invite process."
                        self.log(error_message)
                        if self.on_invite_progress:
                            self.on_invite_progress(invited_count, total_players, error_message)
                        self.is_inviting = False
                        break
                
                # Process next player in queue
                try:
                    # Check stop flag
                    if not self.is_inviting:
                        break
                    
                    player = player_queue.get(block=False)
                    self.log(f"Processing player: {player.display_name} ({player.id})")
                    
                    # Check stop flag again before processing
                    if not self.is_inviting:
                        # Put the player back in the queue
                        player_queue.put(player)
                        break
                    
                    try:
                        # Double-check if player is already in the group or has a pending invite
                        should_invite = True
                        
                        # Check if player is already in the group
                        try:
                            self.log(f"Checking if {player.display_name} is already in group {group_id}...")
                            # Try to get the player's membership status
                            membership = self.groups_api.get_group_member(group_id, player.id)
                            if membership:
                                with lock:
                                    skipped_count += 1
                                    status_message = f"Skipped {player.display_name} - already in group ({invited_count}/{total_players})"
                                    self.log(status_message)
                                    if self.on_invite_progress:
                                        self.on_invite_progress(invited_count, total_players, status_message)
                                should_invite = False
                        except ApiException as e:
                            # 404 means the player is not in the group, which is what we want
                            if e.status != 404:
                                self.log(f"Error checking membership for {player.display_name}: {str(e)}")
                            else:
                                self.log(f"{player.display_name} is not in group {group_id} (404 response, which is expected)")
                        
                        # Check if player already has a pending invite
                        if should_invite:
                            try:
                                self.log(f"Checking if {player.display_name} already has a pending invite to group {group_id}...")
                                # Try to get pending invites for the group
                                pending_invites_response = self.groups_api.get_group_invites(group_id)
                                if pending_invites_response and hasattr(pending_invites_response, 'data'):
                                    pending_invites = [invite.user_id for invite in pending_invites_response.data]
                                    if player.id in pending_invites:
                                        with lock:
                                            skipped_count += 1
                                            status_message = f"Skipped {player.display_name} - already has pending invite ({invited_count}/{total_players})"
                                            self.log(status_message)
                                            if self.on_invite_progress:
                                                self.on_invite_progress(invited_count, total_players, status_message)
                                        should_invite = False
                                    else:
                                        self.log(f"{player.display_name} does not have a pending invite to group {group_id}")
                            except ApiException as e:
                                self.log(f"Error checking pending invites for {player.display_name}: {str(e)}")
                        
                        # Send group invite if all checks pass
                        if should_invite:
                            self.log(f"Sending invite to {player.display_name} ({player.id}) for group {group_id}...")
                            try:
                                # Create the proper request object for the group invite
                                invite_request = CreateGroupInviteRequest(user_id=player.id)
                                
                                # Send the invite with the proper request object
                                invite_response = self.groups_api.create_group_invite(
                                    group_id=group_id,
                                    create_group_invite_request=invite_request
                                )
                                
                                self.log(f"Invite API response: {invite_response}")
                                with lock:
                                    invited_count += 1
                                    status_message = f"Invited {player.display_name} ({invited_count}/{total_players})"
                                    self.log(status_message)
                                    if self.on_invite_progress:
                                        self.on_invite_progress(invited_count, total_players, status_message)
                            except ApiException as e:
                                self.log(f"API Exception when inviting {player.display_name}: {str(e)}")
                                with lock:
                                    failed_count += 1
                                    error_message = f"Failed to invite {player.display_name}: {str(e)}"
                                    self.log(error_message)
                                    # Log more details about the API exception
                                    if hasattr(e, 'status'):
                                        self.log(f"API Exception details - Status: {e.status}, Reason: {e.reason}")
                                    if hasattr(e, 'body') and e.body:
                                        self.log(f"Response body: {e.body}")
                            except Exception as e:
                                self.log(f"Unexpected error inviting {player.display_name}: {str(e)}")
                                with lock:
                                    failed_count += 1
                                    error_message = f"Failed to invite {player.display_name}: {str(e)}"
                                    self.log(error_message)
                                    self.log(f"Exception details: {traceback.format_exc()}")
                    except ApiException as e:
                        with lock:
                            failed_count += 1
                            error_message = f"Failed to invite {player.display_name}: {str(e)}"
                            self.log(error_message)
                            # Log more details about the API exception
                            self.log(f"API Exception details - Status: {e.status}, Reason: {e.reason}")
                            if hasattr(e, 'body') and e.body:
                                self.log(f"Response body: {e.body}")
                    except Exception as e:
                        with lock:
                            failed_count += 1
                            error_message = f"Unexpected error inviting {player.display_name}: {str(e)}"
                            self.log(error_message)
                            self.log(f"Exception details: {traceback.format_exc()}")
                    
                    # Check stop flag before waiting
                    if not self.is_inviting:
                        break
                    
                    # Wait for the specified delay before next invitation (per thread)
                    self.log(f"Waiting {delay_seconds} seconds before processing next player...")
                    time.sleep(delay_seconds)
                except Exception as e:
                    # Queue is empty or other error
                    self.log(f"Worker thread error: {str(e)}")
                    self.log(f"Exception details: {traceback.format_exc()}")
                    break
        
        except Exception as e:
            self.log(f"Error inviting players: {str(e)}")
            self.log(f"Exception details: {traceback.format_exc()}")
            self.is_inviting = False
            return False
        
        # Update status based on whether process was stopped or completed
        if not self.is_inviting:
            completion_message = f"Invitation process stopped. Invited {invited_count}/{total_players} players. Failed: {failed_count}, Skipped: {skipped_count}"
        else:
            completion_message = f"Invitation process completed. Invited {invited_count}/{total_players} players. Failed: {failed_count}, Skipped: {skipped_count}"
        
        self.is_inviting = False
        self.log(completion_message)
        if self.on_invite_progress:
            self.on_invite_progress(invited_count, total_players, completion_message)
        return True