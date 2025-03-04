# main.py
import os
import sys
import logging

import tkinter as tk
from tkinter import messagebox

from gui import VRChatAutoInviteGUI
from logic import VRChatLogic
from plugin_manager import PluginManager
from config import ConfigManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("vrchat_auto_invite.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("VRChatAutoInvite")

def attempt_auto_login(logic_controller, app):
    """Attempt to login using saved credentials"""
    logger.info("Attempting auto-login...")
    
    # Update UI to show we're trying to login
    app.add_log_message("Attempting to login with saved credentials...")
    app.update_login_status("Logging in...", "yellow")
    
    # Try to auto-login
    logic_controller.auto_login(login_result_callback=app.handle_login_result)

def main():
    # Create the root window
    root = tk.Tk()
    
    try:
        # Initialize components
        config_manager = ConfigManager()
        config_manager.load_config()  # Make sure to load the config
        plugin_manager = PluginManager()
        logic_controller = VRChatLogic(config_manager, plugin_manager)
        
        # Create GUI
        app = VRChatAutoInviteGUI(root, logic_controller)
        
        # Set up callbacks from logic to GUI
        logic_controller.set_gui_callbacks(
            update_login_status=app.handle_login_result,
            update_invite_progress=app.update_invite_progress,
            add_log_message=app.add_log_message,
            update_log_watcher_status=app.update_log_watcher_status
        )
        
        # Set app reference in plugin manager
        plugin_manager.set_app(app)
        
        # Load plugins
        plugin_manager.load_plugins_from_directory("plugins")
        app.refresh_plugin_list()
        
        # Load saved configuration
        config = config_manager.load_config()
        if config:
            app.username_var.set(config.get("username", ""))
            app.group_id_var.set(config.get("group_id", ""))
            app.user_file_var.set(config.get("user_file", ""))
            app.delay_var.set(config.get("delay", 5))
            app.threads_var.set(config.get("threads", 5))
        
        # Attempt auto-login after GUI is initialized
        root.after(1000, lambda: attempt_auto_login(logic_controller, app))
        
        # Set up cleanup on window close
        root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root, app, logic_controller, config_manager))
        
        # Start the main loop
        root.mainloop()
        
    except Exception as e:
        logger.error(f"Application error: {str(e)}", exc_info=True)
        messagebox.showerror("Error", f"An error occurred: {str(e)}")

def on_closing(root, app, logic_controller, config_manager):
    """Handle application closing"""
    try:
        # Save configuration if logged in
        if logic_controller.is_logged_in:
            config_manager.save_config({
                "username": app.username_var.get(),
                "group_id": app.group_id_var.get(),
                "user_file": app.user_file_var.get(),
                "delay": app.delay_var.get(),
                "threads": app.threads_var.get()
            })
        
        # Call cleanup methods
        app.cleanup()
        
        # Destroy the root window
        root.destroy()
    except Exception as e:
        logger.error(f"Error during application shutdown: {str(e)}", exc_info=True)
        
if __name__ == "__main__":
    main()