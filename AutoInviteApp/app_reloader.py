import os
import sys
import time
import subprocess
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger("VRChatAutoInvite")

class CodeChangeHandler(FileSystemEventHandler):
    """Handler for detecting changes in Python files"""
    
    def __init__(self, callback):
        self.callback = callback
        self.last_modified = time.time()
        self.cooldown = 2  # Cooldown period in seconds to prevent multiple triggers
        
    def on_modified(self, event):
        # Only trigger for .py files
        if not event.is_directory and event.src_path.endswith('.py'):
            current_time = time.time()
            if current_time - self.last_modified > self.cooldown:
                self.last_modified = current_time
                logger.info(f"Code change detected in {event.src_path}")
                self.callback(event.src_path)

class AppReloader:
    """Handles monitoring for code changes and reloading the application"""
    
    def __init__(self):
        self.observer = None
        self.running = False
        self.change_callback = None
    
    def start_monitoring(self, callback=None):
        """Start monitoring for code changes"""
        if self.running:
            return
            
        self.change_callback = callback
        self.running = True
        
        # Create an observer and event handler
        self.observer = Observer()
        event_handler = CodeChangeHandler(self._on_code_change)
        
        # Get the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Start watching the directory
        self.observer.schedule(event_handler, current_dir, recursive=False)
        self.observer.start()
        
        logger.info(f"Started monitoring for code changes in {current_dir}")
    
    def stop_monitoring(self):
        """Stop monitoring for code changes"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.running = False
            logger.info("Stopped monitoring for code changes")
    
    def _on_code_change(self, file_path):
        """Called when a code change is detected"""
        if self.change_callback:
            self.change_callback(file_path)
    
    def reload_application(self):
        """Restart the application"""
        logger.info("Restarting application...")
        
        # Stop the file monitoring
        self.stop_monitoring()
        
        # Get the current script path
        script_path = os.path.abspath(sys.argv[0])
        
        # Start a new process with the same arguments
        subprocess.Popen([sys.executable, script_path] + sys.argv[1:])
        
        # Exit the current process
        sys.exit(0) 