# VRChat Auto Invite

A powerful tool to easily invite players from your current VRChat instance to groups.

## Features

- **Auto Invite**: Automatically invite players from your current instance to a VRChat group
- **File-Based Invites**: Import a list of usernames from a text file
- **Instance-Based Invites**: Invite all players from your current VRChat instance
- **Customizable Settings**: Configure delay between invites and threading options
- **Plugin System**: Extend functionality with custom plugins
- **Modern UI**: Clean, intuitive interface with light and dark themes
- **Persistent Login**: Remember your login credentials securely between sessions
- **Smart Invites**: Prevents duplicate invites to players who already have pending invites
- **NEW**: Auto-reload feature for easy development and updates

## Installation

### Windows

1. Download the latest release from the [Releases](https://github.com/yourusername/vrchat-auto-invite/releases) page
2. Extract the ZIP file to a location of your choice
3. Run `AutoInvite.bat` to start the application
   - The launcher will automatically check for Python and required dependencies
   - If any dependencies are missing, it will offer to install them for you

### Linux

1. Download the latest release from the [Releases](https://github.com/yourusername/vrchat-auto-invite/releases) page
2. Extract the tarball to a location of your choice
3. Run `run.sh` to start the application

### From Source

If you prefer to run from source:

1. Clone this repository:
   ```
   git clone https://github.com/TitanBCXR/vrchat-auto-invite.git
   cd vrchat-auto-invite
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python main.py
   ```

## Usage

1. Launch the application using `AutoInvite.bat`
2. Log in with your VRChat credentials
   - Optionally check "Remember Me" to save your credentials securely
3. Select a group from the dropdown menu
4. Choose your invite method:
   - **Instance**: Invite players from your current VRChat instance
   - **File**: Import a list of usernames from a text file
5. Configure invite settings (delay, threads)
6. Click "Start Inviting" to begin the process

## Development

The application now includes an auto-reload feature that detects code changes and allows you to reload the application without manually restarting it. When code changes are detected, a "Reload App" button in the top-right corner will become active, allowing you to apply the changes with a single click.

## Requirements

- Python 3.8+
- watchdog (for code change detection)
- pillow (for image processing)
- sv_ttk (for modern UI theme)
- vrchatapi (for VRChat API integration)

## Security

- Credentials are stored securely using encryption
- No data is sent to any third-party servers
- All API calls are made directly to VRChat's official API

## Troubleshooting

If you encounter any issues:

1. Check that you have Python 3.8 or higher installed
2. Ensure all dependencies are installed correctly
3. Verify your VRChat credentials are correct
4. Check the console output for any error messages

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.