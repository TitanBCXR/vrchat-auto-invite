#!/usr/bin/env python3
import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox

def install_package(package_name):
    """Install a Python package using pip"""
    print(f"Installing {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_name}: {e}")
        return False

def main():
    """
    Perform pre-launch checks to ensure the application can run properly.
    Returns True if all checks pass, False otherwise.
    """
    print("Running precheck...")
    
    # Check if Python version is compatible
    if sys.version_info < (3, 8):
        show_error(f"Python 3.8 or higher is required. You are using Python {sys.version.split()[0]}")
        return False
    
    # Check if tkinter is available
    try:
        import tkinter
        from tkinter import ttk
    except ImportError:
        show_error("Tkinter is not available. This application requires tkinter.")
        return False
    
    # Check for required packages
    required_packages = [
        "sv_ttk",
        "cryptography",
        "pillow",  # For PIL/ImageTk
        "vrchatapi"
    ]
    for package in required_packages:
        try:
            __import__(package)
            print(f"Package {package} is installed.")
        except ImportError:
            print(f"Package {package} is not installed.")
            
            # Ask user if they want to install the package
            try:
                root = tk.Tk()
                root.withdraw()
                result = messagebox.askyesno(
                    "Missing Package", 
                    f"The required package '{package}' is not installed. Would you like to install it now?"
                )
                root.destroy()
                
                if result:
                    if not install_package(package):
                        show_error(f"Failed to install {package}. Please install it manually using 'pip install {package}'")
                        return False
                else:
                    show_error(f"Cannot continue without required package: {package}")
                    return False
            except:
                # If GUI fails, try console
                print(f"The required package '{package}' is not installed. Installing automatically...")
                if not install_package(package):
                    show_error(f"Failed to install {package}. Please install it manually using 'pip install {package}'")
                    return False
    
    # Check if required directories exist
    required_dirs = ["assets", "plugins"]
    for directory in required_dirs:
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory)
                print(f"Created missing directory: {directory}")
            except Exception as e:
                show_error(f"Failed to create required directory '{directory}': {str(e)}")
                return False
    
    # Check if required files exist
    required_files = ["main.py", "gui.py", "logic.py", "config.py", "plugin_manager.py"]
    missing_files = [file for file in required_files if not os.path.isfile(file)]
    
    if missing_files:
        show_error(f"Missing required files: {', '.join(missing_files)}")
        return False
    
    # All checks passed
    print("All precheck tests passed successfully.")
    return True

def show_error(message):
    """Show an error message using a GUI dialog or console depending on availability"""
    print(f"Error: {message}")  # Always try to print to console
    
    try:
        # Try to show a GUI message box
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        messagebox.showerror("Error", message)
        root.destroy()
    except:
        # If GUI fails, we already printed to console
        pass

if __name__ == "__main__":
    # Run the precheck and exit with appropriate code
    success = main()
    sys.exit(0 if success else 1)