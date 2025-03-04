# plugins/example_plugin.py
import tkinter as tk
from tkinter import ttk, messagebox
from plugin_manager import Plugin

class ExamplePlugin(Plugin):
    def __init__(self, app=None):
        super().__init__(app)
        self.name = "Example Plugin"
        self.version = "1.0.0"
        self.description = "An example plugin that demonstrates the plugin system"
        self.author = "Your Name"
        
    def initialize(self):
        """Initialize the plugin"""
        # You can do any setup here
        pass
        
    def create_tab(self, notebook):
        """Create a tab for the plugin in the notebook"""
        # Create a new tab
        self.tab = ttk.Frame(notebook)
        notebook.add(self.tab, text=self.name)
        
        # Add content to the tab
        ttk.Label(self.tab, text="This is an example plugin tab").pack(padx=10, pady=10)
        ttk.Button(self.tab, text="Click Me", command=self.on_button_click).pack(padx=10, pady=10)
        
    def on_button_click(self):
        """Handle button click"""
        messagebox.showinfo("Example Plugin", "Button clicked!")
        
        # You can access the app through self.app
        if self.app and hasattr(self.app, 'add_log_message'):
            self.app.add_log_message("Example plugin button clicked")