# gui.py
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime
import sv_ttk  # Modern theme for ttk (Sun Valley theme)
from PIL import Image, ImageTk  # For handling images
import webbrowser  # For opening links
from app_reloader import AppReloader  # Import the app reloader

class ModernTooltip:
    """Modern tooltip implementation"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
        
    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        # Create a toplevel window
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        # Create tooltip content
        frame = ttk.Frame(self.tooltip, borderwidth=1, relief="solid")
        frame.pack(fill="both", expand=True)
        
        label = ttk.Label(frame, text=self.text, wraplength=250, 
                          justify="left", padding=(5, 5))
        label.pack()
        
    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class VRChatAutoInviteGUI:
    def __init__(self, root, logic_controller):
        self.root = root
        self.logic = logic_controller
        
        # Set up the main window
        self.root.title("VRChat Auto Invite")
        
        # Apply modern theme
        sv_ttk.set_theme("dark")  # Use "light" or "dark"
        
        # Initialize variables
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.remember_me_var = tk.BooleanVar(value=False)
        self.group_id_var = tk.StringVar()
        self.user_file_var = tk.StringVar()
        self.delay_var = tk.IntVar(value=5)
        self.threads_var = tk.IntVar(value=5)
        self.invite_source_var = tk.StringVar(value="file")
        self.login_status_var = tk.StringVar(value="Not logged in")
        self.progress_var = tk.StringVar(value="Ready")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_log)
        
        # Initialize app reloader
        self.app_reloader = AppReloader()
        
        # Load images
        self.load_images()
        
        # Create UI components
        self.create_ui()
        
        # Set up status bar
        self.create_status_bar()
        
        # Calculate dynamic window size based on required size after UI creation
        self.root.update_idletasks()
        req_width = self.root.winfo_reqwidth()
        req_height = self.root.winfo_reqheight()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = min(max(req_width, int(screen_width * 0.8)), screen_width)
        window_height = min(max(req_height, int(screen_height * 0.8)), screen_height)
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.minsize(req_width, req_height)
        
        # Start monitoring for code changes
        self.app_reloader.start_monitoring(self.on_code_change_detected)
        
        # Schedule a check of the log watcher status after UI is fully loaded
        self.root.after(1000, self.update_log_watcher_status)
        
    def load_images(self):
        """Load images for the UI"""
        try:
            # Try to load logo
            self.logo_img = ImageTk.PhotoImage(Image.open("assets/logo.png").resize((150, 150)))
        except:
            # Create a placeholder if image not found
            self.logo_img = None
            
        # Load icons for buttons
        try:
            self.login_icon = ImageTk.PhotoImage(Image.open("assets/login.png").resize((16, 16)))
            self.start_icon = ImageTk.PhotoImage(Image.open("assets/start.png").resize((16, 16)))
            self.stop_icon = ImageTk.PhotoImage(Image.open("assets/stop.png").resize((16, 16)))
            self.browse_icon = ImageTk.PhotoImage(Image.open("assets/browse.png").resize((16, 16)))
        except:
            self.login_icon = None
            self.start_icon = None
            self.stop_icon = None
            self.browse_icon = None
        
    def create_ui(self):
        """Create the user interface"""
        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create header with logo
        self.create_header()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Main tab
        self.main_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.main_frame, text="Auto Invite")
        
        # Create login frame
        self.create_login_frame()
        
        # Create invite settings frame
        self.create_invite_frame()
        
        # Create progress frame
        self.create_progress_frame()
        
        # Create log frame
        self.create_log_frame()
        
        # Create plugins tab
        self.plugins_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.plugins_frame, text="Plugins")
        self.create_plugins_tab()
        
        # Create settings tab
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings")
        self.create_settings_tab()
        
        # Create about tab
        self.about_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.about_frame, text="About")
        self.create_about_tab()
        
    def create_header(self):
        """Create header with logo and title"""
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Add logo if available
        if self.logo_img:
            logo_label = ttk.Label(header_frame, image=self.logo_img)
            logo_label.pack(side=tk.LEFT, padx=10)
        
        # Add title and description
        title_frame = ttk.Frame(header_frame)
        title_frame.pack(side=tk.LEFT, padx=10)
        
        title_label = ttk.Label(title_frame, text="VRChat Auto Invite", 
                               font=("Segoe UI", 18, "bold"))
        title_label.pack(anchor=tk.W)
        
        desc_label = ttk.Label(title_frame, 
                              text="Easily invite players from your current instance to groups",
                              font=("Segoe UI", 10))
        desc_label.pack(anchor=tk.W)
        
        # Add reload button to the right side
        reload_frame = ttk.Frame(header_frame)
        reload_frame.pack(side=tk.RIGHT, padx=10)
        
        # Try to load reload icon
        try:
            self.reload_icon = ImageTk.PhotoImage(Image.open("assets/reload_small.png"))
        except:
            self.reload_icon = None
        
        self.reload_button = ttk.Button(reload_frame, text="Reload App", 
                                      command=self.prompt_reload_app,
                                      image=self.reload_icon, compound=tk.LEFT)
        self.reload_button.pack(side=tk.RIGHT)
        ModernTooltip(self.reload_button, "Reload the application to apply code changes")
        
        # Initially disable the reload button (will be enabled when changes are detected)
        self.reload_button.config(state="disabled")
        
    def create_login_frame(self):
        """Create the login frame"""
        login_frame = ttk.LabelFrame(self.main_frame, text="VRChat Account")
        login_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Create a grid layout
        login_frame.columnconfigure(1, weight=1)
        
        # Username
        ttk.Label(login_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        username_entry = ttk.Entry(login_frame, textvariable=self.username_var)
        username_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W+tk.E)
        ModernTooltip(username_entry, "Enter your VRChat username or email")
        
        # Password
        ttk.Label(login_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        password_entry = ttk.Entry(login_frame, textvariable=self.password_var, show="•")
        password_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W+tk.E)
        ModernTooltip(password_entry, "Enter your VRChat password")
        
        # Remember Me checkbox
        remember_me_check = ttk.Checkbutton(login_frame, text="Remember Me", 
                                           variable=self.remember_me_var)
        remember_me_check.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        ModernTooltip(remember_me_check, "Save login credentials securely for automatic login")
        
        # Login button
        button_frame = ttk.Frame(login_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        self.login_button = ttk.Button(button_frame, text="Login", command=self.handle_login,
                                     image=self.login_icon, compound=tk.LEFT)
        self.login_button.pack(side=tk.LEFT, padx=5)
        
        self.logout_button = ttk.Button(button_frame, text="Logout", command=self.handle_logout,
                                      compound=tk.LEFT)
        self.logout_button.pack(side=tk.LEFT, padx=5)
        self.logout_button.config(state=tk.DISABLED)  # Disabled until logged in
        
        # Status
        status_frame = ttk.Frame(login_frame)
        status_frame.grid(row=4, column=0, columnspan=2, sticky=tk.W+tk.E)
        
        self.status_indicator = ttk.Label(status_frame, text="●", foreground="red")
        self.status_indicator.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(status_frame, textvariable=self.login_status_var).pack(side=tk.LEFT)
        
    def create_invite_frame(self):
        """Create the invite settings frame"""
        invite_frame = ttk.LabelFrame(self.main_frame, text="Group Invite Settings")
        invite_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Configure grid
        invite_frame.columnconfigure(1, weight=1)
        
        # Source selection
        source_frame = ttk.Frame(invite_frame)
        source_frame.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(source_frame, text="Invite Source:").pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Radiobutton(source_frame, text="From File", variable=self.invite_source_var, 
                      value="file", command=self.toggle_invite_source).pack(side=tk.LEFT, padx=5)
        
        ttk.Radiobutton(source_frame, text="From Current Instance", variable=self.invite_source_var, 
                      value="instance", command=self.toggle_invite_source).pack(side=tk.LEFT, padx=5)
        
        # Group ID
        ttk.Label(invite_frame, text="Group ID:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        group_id_entry = ttk.Entry(invite_frame, textvariable=self.group_id_var)
        group_id_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        ModernTooltip(group_id_entry, "Enter the VRChat Group ID you want to invite players to")
        
        # User file (for file-based invites)
        self.user_file_label = ttk.Label(invite_frame, text="User List File:")
        self.user_file_label.grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        
        self.user_file_entry = ttk.Entry(invite_frame, textvariable=self.user_file_var, state="readonly")
        self.user_file_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W+tk.E)
        
        self.browse_button = ttk.Button(invite_frame, text="Browse", command=self.browse_user_file,
                                      image=self.browse_icon, compound=tk.LEFT)
        self.browse_button.grid(row=2, column=2, padx=5, pady=5)
        
        # Threading settings (for instance-based invites)
        self.threads_label = ttk.Label(invite_frame, text="Max Threads:")
        self.threads_label.grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        
        self.threads_spinbox = ttk.Spinbox(invite_frame, from_=1, to=10, textvariable=self.threads_var)
        self.threads_spinbox.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        ModernTooltip(self.threads_spinbox, "Number of parallel invitation threads (higher = faster but may hit rate limits)")
        
        # Delay settings
        ttk.Label(invite_frame, text="Delay (seconds):").grid(row=4, column=0, padx=5, pady=5, sticky=tk.W)
        delay_spinbox = ttk.Spinbox(invite_frame, from_=1, to=60, textvariable=self.delay_var)
        delay_spinbox.grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W+tk.E)
        ModernTooltip(delay_spinbox, "Delay between invitations to avoid rate limits")
        
        # Log watcher status
        log_watcher_status_frame = ttk.Frame(invite_frame)
        log_watcher_status_frame.grid(row=5, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W+tk.E)
        
        self.log_watcher_status = ttk.Label(log_watcher_status_frame, text="Log Watcher: Inactive")
        self.log_watcher_status.pack(side=tk.RIGHT, padx=5)
        
        # Start/Stop buttons
        button_frame = ttk.Frame(invite_frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=10)
        
        self.start_button = ttk.Button(button_frame, text="Start Inviting", command=self.handle_start_inviting,
                                     image=self.start_icon, compound=tk.LEFT)
        self.start_button.pack(side=tk.LEFT, padx=5)
        ModernTooltip(self.start_button, "Start inviting players and watching VRChat logs")
        
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.handle_stop_inviting,
                                    image=self.stop_icon, compound=tk.LEFT, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        ModernTooltip(self.stop_button, "Stop inviting players and log watching")
        
        # Initialize the source toggle
        self.toggle_invite_source()
    
    def create_progress_frame(self):
        """Create the progress frame"""
        progress_frame = ttk.LabelFrame(self.main_frame, text="Progress")
        progress_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(padx=5, pady=5, anchor=tk.W)
        
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, mode="determinate")
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
    def create_log_frame(self):
        """Create the log frame"""
        log_frame = ttk.LabelFrame(self.main_frame, text="Activity Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Search bar
        search_frame = ttk.Frame(log_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Clear button
        ttk.Button(search_frame, text="Clear Log", command=self.clear_log).pack(side=tk.RIGHT, padx=5)
        
        # Log text area
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_container, height=10, wrap=tk.WORD, bg="#2d2d2d", fg="#ffffff")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_container, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Configure tag for search highlighting
        self.log_text.tag_configure("highlight", background="#555500")
    
    def handle_stop_inviting(self):
        """Handle stop button click"""
        # Stop inviting process if running
        if self.logic.stop_inviting():
            self.add_log_message("Stopping invitation process...")
        
        # Stop log watcher
        if self.logic.is_log_watching():
            if self.logic.stop_log_watching():
                self.add_log_message("Stopped VRChat log watcher")
            else:
                self.add_log_message("Failed to stop VRChat log watcher")
        
        # Update button states
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_text.config(text="Ready")
        
        # Update log watcher status
        self.update_log_watcher_status()
    
    def update_invite_progress(self, current, total, message):
        """Update the invitation progress"""
        if total > 0:
            progress_percent = (current / total) * 100
            self.progress_bar["value"] = progress_percent
        self.progress_var.set(message)
        
        # If process is complete or stopped, update status but don't change button states
        # since the log watcher may still be running
        if current == total or "completed" in message.lower() or "stopped" in message.lower():
            self.add_log_message(f"Invitation progress: {message}")
            if self.logic.is_log_watching():
                self.status_text.config(text="Log watcher still running")
            else:
                self.status_text.config(text="Ready")
                self.start_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)
    
    def create_plugins_tab(self):
        """Create the plugins tab"""
        # Plugin management frame
        plugin_mgmt_frame = ttk.Frame(self.plugins_frame)
        plugin_mgmt_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(plugin_mgmt_frame, text="Load Plugin", command=self.handle_load_plugin).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(plugin_mgmt_frame, text="Refresh Plugins", command=self.handle_refresh_plugins).pack(side=tk.LEFT, padx=5, pady=5)
        
        # Plugin list frame
        plugin_list_frame = ttk.LabelFrame(self.plugins_frame, text="Installed Plugins")
        plugin_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create a two-pane view
        plugin_panes = ttk.PanedWindow(plugin_list_frame, orient=tk.HORIZONTAL)
        plugin_panes.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left pane: Plugin list
        left_frame = ttk.Frame(plugin_panes)
        plugin_panes.add(left_frame, weight=1)
        
        self.plugin_listbox = tk.Listbox(left_frame, bg="#2d2d2d", fg="#ffffff", 
                                        selectbackground="#555555", selectforeground="#ffffff")
        self.plugin_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        plugin_scrollbar = ttk.Scrollbar(left_frame, command=self.plugin_listbox.yview)
        plugin_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.plugin_listbox.config(yscrollcommand=plugin_scrollbar.set)
        
        # Right pane: Plugin details
        right_frame = ttk.Frame(plugin_panes)
        plugin_panes.add(right_frame, weight=2)
        
        self.plugin_details_text = tk.Text(right_frame, height=10, wrap=tk.WORD, 
                                         bg="#2d2d2d", fg="#ffffff")
        self.plugin_details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        plugin_details_scrollbar = ttk.Scrollbar(right_frame, command=self.plugin_details_text.yview)
        plugin_details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.plugin_details_text.config(yscrollcommand=plugin_details_scrollbar.set)
        
        # Bind plugin selection event
        self.plugin_listbox.bind('<<ListboxSelect>>', self.handle_plugin_selection)
        
    def create_settings_tab(self):
        """Create the settings tab"""
        settings_container = ttk.Frame(self.settings_frame)
        settings_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Theme settings
        theme_frame = ttk.LabelFrame(settings_container, text="Appearance")
        theme_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(theme_frame, text="Theme:").pack(side=tk.LEFT, padx=5, pady=10)
        
        theme_var = tk.StringVar(value="dark")
        ttk.Radiobutton(theme_frame, text="Light", variable=theme_var, value="light", 
                       command=lambda: sv_ttk.set_theme("light")).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(theme_frame, text="Dark", variable=theme_var, value="dark", 
                       command=lambda: sv_ttk.set_theme("dark")).pack(side=tk.LEFT, padx=5)
        
        # API settings
        api_frame = ttk.LabelFrame(settings_container, text="API Settings")
        api_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(api_frame, text="API Timeout (seconds):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Spinbox(api_frame, from_=5, to=60, increment=5).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(api_frame, text="User Agent:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(api_frame).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W+tk.E)
        
        # Save settings button
        ttk.Button(settings_container, text="Save Settings", command=self.save_settings).pack(pady=10)
        
    def create_about_tab(self):
        """Create the about tab"""
        about_container = ttk.Frame(self.about_frame)
        about_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # App info
        if self.logo_img:
            ttk.Label(about_container, image=self.logo_img).pack(pady=10)
            
        ttk.Label(about_container, text="VRChat Auto Invite", 
                font=("Segoe UI", 16, "bold")).pack()
        ttk.Label(about_container, text="Version 1.0.0").pack()
        ttk.Label(about_container, text="© 2025 Titan_BCXR").pack()
        
        # Description
        desc_frame = ttk.LabelFrame(about_container, text="Description")
        desc_frame.pack(fill=tk.X, padx=5, pady=10)
        
        description = """
        VRChat Auto Invite is a tool that helps you invite multiple users to your VRChat groups.
        You can invite users from a file or from your current instance.
        
        This application uses the official VRChat API and respects rate limits to avoid account bans.
        """
        
        ttk.Label(desc_frame, text=description, wraplength=600, justify="center").pack(padx=10, pady=10)
        
        # Links
        links_frame = ttk.Frame(about_container)
        links_frame.pack(pady=10)
        
        ttk.Button(links_frame, text="GitHub Repository", 
                 command=lambda: webbrowser.open("https://github.com/TitanBCXR/vrchat-auto-invite")).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(links_frame, text="Report an Issue", 
                 command=lambda: webbrowser.open("https://github.com/TitanBCXR/vrchat-auto-invite/issues")).pack(side=tk.LEFT, padx=5)
        
    def create_status_bar(self):
        """Create status bar at the bottom of the window"""
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(5, 2))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_text = ttk.Label(self.status_bar, text="Ready")
        self.status_text.pack(side=tk.LEFT)
        
        self.version_label = ttk.Label(self.status_bar, text="v1.0.0")
        self.version_label.pack(side=tk.RIGHT)
        
    def toggle_invite_source(self):
        """Toggle between file and instance invite sources"""
        if self.invite_source_var.get() == "file":
            # Enable file selection, disable threading
            self.user_file_label.config(state="normal")
            self.user_file_entry.config(state="readonly")
            self.browse_button.config(state="normal")
            self.threads_label.config(state="disabled")
            self.threads_spinbox.config(state="disabled")
        else:
            # Disable file selection, enable threading
            self.user_file_label.config(state="disabled")
            self.user_file_entry.config(state="disabled")
            self.browse_button.config(state="disabled")
            self.threads_label.config(state="normal")
            self.threads_spinbox.config(state="normal")
            
    def handle_login(self):
        """Handle login button click"""
        username = self.username_var.get()
        password = self.password_var.get()
        remember_me = self.remember_me_var.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Username and password are required")
            return
        
        # Update UI to show login in progress
        self.update_login_status("Logging in...", "yellow")
        
        # Call the logic controller to handle login
        self.logic.login(username, password, self.handle_2fa_request, self.handle_login_result, remember_me)
        
    def handle_2fa_request(self, is_email_2fa=False):
        """Handle 2FA request with a custom dialog"""
        self.add_log_message(f"2FA requested: {'Email' if is_email_2fa else 'Authenticator'}")
        dialog = TwoFactorAuthDialog(self.root, is_email_2fa)
        code = dialog.result
        self.add_log_message(f"2FA code entered: {'Yes' if code else 'No/Cancelled'}")
        return code
        
    def handle_login_result(self, success, message):
        """Handle login result"""
        if success:
            self.update_login_status(message, "green")
            self.add_log_message(f"Successfully logged in: {message}")
        else:
            self.update_login_status(message, "red")
            self.add_log_message(f"Login failed: {message}")
        
    def browse_user_file(self):
        """Open file dialog to select user list file"""
        file_path = filedialog.askopenfilename(
            title="Select User List File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.user_file_var.set(file_path)
            
    def handle_start_inviting(self):
        """Handle start inviting button click"""
        group_id = self.group_id_var.get()
        delay = self.delay_var.get()
        
        # First, start the log watcher if it's not already running
        if not self.logic.is_log_watching():
            self.add_log_message("Starting VRChat log watcher with initial log scan")
            success = self.logic.start_log_watching(scan_existing=True)
            if not success:
                self.add_log_message("Failed to start log watcher, but will continue with one-time log scan")
        
        # If a group ID is provided, start inviting players
        if group_id:
            success = False
            if self.invite_source_var.get() == "file":
                user_file = self.user_file_var.get()
                if not user_file or not os.path.exists(user_file):
                    messagebox.showerror("Error", "Please select a valid user list file")
                    return
                success = self.logic.start_inviting(group_id, user_file, delay)
            else:
                max_threads = self.threads_var.get()
                success = self.logic.invite_instance_players_to_group(group_id, max_threads, delay)
            
            if success:
                self.add_log_message(f"Starting invitations to group {group_id}")
                self.progress_var.set("Starting invitations...")
                self.progress_bar["value"] = 0
                self.status_text.config(text="Inviting users...")
        else:
            # If no group ID, just start the log watcher
            self.add_log_message("No group ID provided, only watching logs")
            self.status_text.config(text="Log watcher running")
        
        # Update button states
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Update log watcher status
        self.update_log_watcher_status()
        
    def update_log_watcher_status(self):
        """Update the log watcher status display"""
        if self.logic.is_log_watching():
            self.log_watcher_status.config(text="Log Watcher: Active")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
        else:
            self.log_watcher_status.config(text="Log Watcher: Inactive")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
        
    def add_log_message(self, message):
        """Add message to log text widget"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        
        # Apply search highlighting if needed
        self.filter_log()
        
    def clear_log(self):
        """Clear the log text widget"""
        self.log_text.delete(1.0, tk.END)
    
    def filter_log(self, *args):
        """Filter log based on search text"""
        search_text = self.search_var.get().lower()
        
        # Remove all existing highlights
        self.log_text.tag_remove("highlight", "1.0", tk.END)
        
        if not search_text:
            return
            
        # Find and highlight all occurrences
        start_pos = "1.0"
        while True:
            start_pos = self.log_text.search(search_text, start_pos, tk.END, nocase=True)
            if not start_pos:
                break
                
            end_pos = f"{start_pos}+{len(search_text)}c"
            self.log_text.tag_add("highlight", start_pos, end_pos)
            start_pos = end_pos
            
    def handle_plugin_selection(self, event):
        """Handle plugin selection in listbox"""
        selection = self.plugin_listbox.curselection()
        if selection:
            plugin_name = self.plugin_listbox.get(selection[0])
            plugin_info = self.logic.get_plugin_info(plugin_name)
            
            if plugin_info:
                self.plugin_details_text.delete(1.0, tk.END)
                
                details = f"Name: {plugin_info.get('name', 'Unknown')}\n"
                details += f"Version: {plugin_info.get('version', 'Unknown')}\n"
                details += f"Author: {plugin_info.get('author', 'Unknown')}\n\n"
                details += f"Description: {plugin_info.get('description', 'No description available')}\n\n"
                
                # Add plugin actions if available
                if 'actions' in plugin_info and plugin_info['actions']:
                    details += "Actions:\n"
                    for action in plugin_info['actions']:
                        details += f"- {action}\n"
                
                self.plugin_details_text.insert(tk.END, details)
                
    def handle_load_plugin(self):
        """Handle load plugin button click"""
        file_path = filedialog.askopenfilename(
            title="Select Plugin File",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        if file_path:
            success, message = self.logic.load_plugin_from_file(file_path)
            if success:
                self.add_log_message(f"Plugin loaded: {message}")
                self.refresh_plugin_list()
            else:
                messagebox.showerror("Error", f"Failed to load plugin: {message}")
                self.add_log_message(f"Failed to load plugin: {message}")
                
    def handle_refresh_plugins(self):
        """Handle refresh plugins button click"""
        count = self.logic.refresh_plugins()
        self.add_log_message(f"Refreshed plugins: {count} plugins loaded")
        self.refresh_plugin_list()
        
    def refresh_plugin_list(self):
        """Refresh the plugin list"""
        if hasattr(self, 'plugin_listbox'):
            self.plugin_listbox.delete(0, tk.END)
            
            for plugin_name in self.logic.get_plugin_names():
                self.plugin_listbox.insert(tk.END, plugin_name)
                
    def save_settings(self):
        """Save application settings"""
        # Implement settings saving logic here
        messagebox.showinfo("Settings", "Settings saved successfully")
        self.add_log_message("Settings saved")

    def handle_logout(self):
        """Handle logout button click"""
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to log out?"):
            clear_saved = False
            if self.logic.config_manager and self.logic.config_manager.get_credentials()[0]:
                clear_saved = messagebox.askyesno("Clear Saved Credentials", 
                                                "Do you also want to clear your saved login credentials?")
            
            self.logic.logout(clear_saved_credentials=clear_saved)
            self.login_button.config(state=tk.NORMAL)
            self.logout_button.config(state=tk.DISABLED)

    def update_login_status(self, message, color="red"):
        """Update the login status UI elements"""
        self.login_status_var.set(message)
        self.status_indicator.config(foreground=color)
        self.status_text.config(text=message)
        
        # Update button states based on login status
        if color == "green":  # Logged in
            self.login_button.config(state=tk.DISABLED)
            self.logout_button.config(state=tk.NORMAL)
        else:  # Not logged in or in progress
            self.login_button.config(state=tk.NORMAL if color != "yellow" else tk.DISABLED)
            self.logout_button.config(state=tk.DISABLED)

    def on_code_change_detected(self, file_path):
        """Called when a code change is detected"""
        # Enable the reload button
        self.reload_button.config(state="normal")
        
        # Show a notification in the log
        self.add_log_message(f"Code change detected in {os.path.basename(file_path)}.")
        self.add_log_message("Click 'Reload App' button in the top-right corner to apply changes.")
        
        # Flash the reload button to draw attention
        self.flash_reload_button()
    
    def flash_reload_button(self, count=0):
        """Flash the reload button to draw attention"""
        if count >= 10:  # Stop after 5 flashes (10 state changes)
            return
        
        # Toggle between normal and accent color
        if count % 2 == 0:
            self.reload_button.state(["pressed"])
        else:
            self.reload_button.state(["!pressed"])
        
        # Schedule the next flash
        self.root.after(500, lambda: self.flash_reload_button(count + 1))
    
    def prompt_reload_app(self):
        """Prompt the user to reload the application"""
        response = messagebox.askyesno(
            "Reload Application",
            "Code changes have been detected. Would you like to reload the application now?\n\n"
            "Note: Any unsaved data will be lost.",
            icon="question"
        )
        
        if response:
            # Save any important state if needed
            self.add_log_message("Reloading application...")
            
            # Schedule the reload after a short delay to allow the message to be displayed
            self.root.after(500, self.app_reloader.reload_application)

    def cleanup(self):
        """Clean up resources before closing"""
        # Stop the app reloader
        if hasattr(self, 'app_reloader'):
            self.app_reloader.stop_monitoring()
        
        # Clean up logic controller
        if self.logic:
            self.logic.cleanup()

class TwoFactorAuthDialog:
    """Modern 2FA authentication dialog"""
    def __init__(self, parent, is_email_2fa=False):
        self.result = None
        
        # Create a modal dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Two-Factor Authentication Required")
        self.dialog.geometry("400x300")
        self.dialog.resizable(False, False)
        
        # Make it modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog on parent
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        dialog_width = 400
        dialog_height = 300
        
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        # Create the content
        self.create_widgets(is_email_2fa)
        
        # Wait for the dialog to be closed
        parent.wait_window(self.dialog)
    
    def create_widgets(self, is_email_2fa):
        """Create the dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Icon or image (you can replace with your own)
        try:
            self.lock_img = ImageTk.PhotoImage(Image.open("assets/2fa.png").resize((64, 64)))
            ttk.Label(main_frame, image=self.lock_img).pack(pady=(0, 15))
        except:
            pass  # No image available
        
        # Title
        auth_type = "Email" if is_email_2fa else "Authenticator App"
        ttk.Label(
            main_frame, 
            text=f"{auth_type} Verification Required", 
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(0, 5))
        
        # Instructions
        if is_email_2fa:
            instructions = "Please check your email for a verification code and enter it below."
        else:
            instructions = "Please enter the verification code from your authenticator app."
        
        ttk.Label(
            main_frame, 
            text=instructions,
            wraplength=350, 
            justify="center"
        ).pack(pady=(0, 15))
        
        # Code entry
        code_frame = ttk.Frame(main_frame)
        code_frame.pack(pady=5)
        
        ttk.Label(code_frame, text="Code:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.code_var = tk.StringVar()
        self.code_entry = ttk.Entry(code_frame, textvariable=self.code_var, width=15, font=("Segoe UI", 12))
        self.code_entry.pack(side=tk.LEFT)
        self.code_entry.focus_set()  # Set focus to the entry
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20, fill=tk.X)
        
        ttk.Button(
            button_frame, 
            text="Cancel", 
            command=self.handle_cancel,
            style="Secondary.TButton"
        ).pack(side=tk.LEFT, padx=5, expand=True)
        
        ttk.Button(
            button_frame, 
            text="Verify", 
            command=self.handle_verify,
            style="Accent.TButton"
        ).pack(side=tk.RIGHT, padx=5, expand=True)
        
        # Bind Enter key to verify
        self.dialog.bind("<Return>", lambda event: self.handle_verify())
        self.dialog.bind("<Escape>", lambda event: self.handle_cancel())
    
    def handle_verify(self):
        """Handle verification button click"""
        code = self.code_var.get().strip()
        if not code:
            messagebox.showerror("Error", "Please enter the verification code", parent=self.dialog)
            return
        
        self.result = code
        self.dialog.destroy()
    
    def handle_cancel(self):
        """Handle cancel button click"""
        self.result = None
        self.dialog.destroy()
