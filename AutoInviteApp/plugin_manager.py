# plugin_manager.py
import os
import sys
import importlib.util
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger("VRChatAutoInvite.PluginManager")

class Plugin:
    """Base class for plugins"""
    def __init__(self, app=None):
        self.app = app
        self.name = "Base Plugin"
        self.version = "1.0.0"
        self.description = "Base plugin class"
        self.author = "Unknown"
        
    def initialize(self):
        """Initialize the plugin"""
        pass
        
    def get_info(self):
        """Get plugin information"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author
        }
        
    def create_tab(self, notebook):
        """Create a tab for the plugin in the notebook"""
        pass

class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.app = None
        
    def set_app(self, app):
        """Set the application instance for plugins to use"""
        self.app = app
        
        # Update existing plugins with app reference
        for plugin in self.plugins.values():
            plugin.app = app
            
    def load_plugin_from_file(self, file_path: str) -> Tuple[bool, str]:
        """Load a plugin from a file"""
        try:
            # Get the module name from the file path
            module_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None:
                return False, f"Could not load plugin spec from {file_path}"
                
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find plugin class (subclass of Plugin)
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                    plugin_class = attr
                    break
                    
            if plugin_class is None:
                return False, f"No Plugin subclass found in {file_path}"
                
            # Create plugin instance
            plugin = plugin_class(self.app)
            plugin_name = plugin.name
            
            # Initialize the plugin
            plugin.initialize()
            
            # Add to plugins dictionary
            self.plugins[plugin_name] = plugin
            
            return True, plugin_name
            
        except Exception as e:
            logger.error(f"Error loading plugin from {file_path}: {str(e)}", exc_info=True)
            return False, str(e)
            
    def load_plugins_from_directory(self, directory: str) -> int:
        """Load all plugins from a directory"""
        if not os.path.exists(directory):
            os.makedirs(directory)
            return 0
            
        count = 0
        for filename in os.listdir(directory):
            if filename.endswith(".py") and not filename.startswith("__"):
                file_path = os.path.join(directory, filename)
                success, message = self.load_plugin_from_file(file_path)
                if success:
                    count += 1
                    logger.info(f"Loaded plugin: {message}")
                else:
                    logger.error(f"Failed to load plugin {filename}: {message}")
                    
        return count
        
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name"""
        return self.plugins.get(name)
        
    def get_plugin_names(self) -> List[str]:
        """Get a list of all plugin names"""
        return list(self.plugins.keys())
        
    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a plugin"""
        plugin = self.get_plugin(name)
        if plugin:
            return plugin.get_info()
        return None