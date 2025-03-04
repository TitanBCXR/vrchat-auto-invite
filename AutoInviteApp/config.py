# config.py
import os
import json
import logging
from typing import Dict, Any, Optional
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("VRChatAutoInvite.ConfigManager")

class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = {}
        self._encryption_key = None
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"Loaded configuration from {self.config_file}")
            else:
                logger.info(f"Configuration file {self.config_file} not found, using defaults")
                self.config = {}
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            self.config = {}
            
        return self.config
        
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file"""
        try:
            self.config = config
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Saved configuration to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False
            
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.config.get(key, default)
        
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value"""
        self.config[key] = value
        
    def update(self, config_dict: Dict[str, Any]) -> None:
        """Update multiple configuration values"""
        self.config.update(config_dict)
        
    def _initialize_encryption(self):
        """Initialize encryption for secure storage"""
        if self._encryption_key is None:
            # Use a machine-specific value as salt
            # This ties the encryption to this machine
            machine_id = self._get_machine_id()
            salt = machine_id.encode()
            
            # Use a fixed passphrase combined with machine ID
            passphrase = "VRChatAutoInvite_SecureStorage"
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
            self._encryption_key = key
            
    def _get_machine_id(self):
        """Get a unique machine identifier"""
        try:
            # Try to get a machine-specific ID
            if os.name == 'nt':  # Windows
                import winreg
                registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                return machine_guid
            else:  # Linux/Mac
                with open('/etc/machine-id', 'r') as f:
                    return f.read().strip()
        except:
            # Fallback to a directory-based ID
            app_dir = os.path.dirname(os.path.abspath(self.config_file))
            return app_dir
            
    def save_auth_token(self, auth_token):
        """Securely save authentication token"""
        try:
            self._initialize_encryption()
            fernet = Fernet(self._encryption_key)
            encrypted_token = fernet.encrypt(auth_token.encode())
            self.set('auth_token', encrypted_token.decode())
            self.save_config(self.config)
            logger.info("Saved authentication token")
            return True
        except Exception as e:
            logger.error(f"Error saving authentication token: {str(e)}")
            return False
            
    def get_auth_token(self):
        """Retrieve securely stored authentication token"""
        try:
            encrypted_token = self.get('auth_token')
            if not encrypted_token:
                return None
                
            self._initialize_encryption()
            fernet = Fernet(self._encryption_key)
            decrypted_token = fernet.decrypt(encrypted_token.encode())
            return decrypted_token.decode()
        except Exception as e:
            logger.error(f"Error retrieving authentication token: {str(e)}")
            return None
            
    def save_credentials(self, username, password):
        """Securely save login credentials"""
        try:
            self._initialize_encryption()
            fernet = Fernet(self._encryption_key)
            
            # Encrypt username and password
            encrypted_username = fernet.encrypt(username.encode()).decode()
            encrypted_password = fernet.encrypt(password.encode()).decode()
            
            # Store in config
            self.set('username', encrypted_username)
            self.set('password', encrypted_password)
            self.save_config(self.config)
            logger.info("Saved login credentials")
            return True
        except Exception as e:
            logger.error(f"Error saving credentials: {str(e)}")
            return False
            
    def get_credentials(self):
        """Retrieve securely stored credentials"""
        try:
            encrypted_username = self.get('username')
            encrypted_password = self.get('password')
            
            if not encrypted_username or not encrypted_password:
                return None, None
                
            self._initialize_encryption()
            fernet = Fernet(self._encryption_key)
            
            # Decrypt username and password
            username = fernet.decrypt(encrypted_username.encode()).decode()
            password = fernet.decrypt(encrypted_password.encode()).decode()
            
            return username, password
        except Exception as e:
            logger.error(f"Error retrieving credentials: {str(e)}")
            return None, None
            
    def clear_saved_login(self):
        """Clear saved login information"""
        if 'auth_token' in self.config:
            del self.config['auth_token']
        if 'username' in self.config:
            del self.config['username']
        if 'password' in self.config:
            del self.config['password']
        self.save_config(self.config)
        logger.info("Cleared saved login information")