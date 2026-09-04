# CSV Sync Service

A Python-based synchronization service that automatically detects and uploads modified CSV files to a server. Designed to work seamlessly with nginx, PHP 8.3, and MariaDB.

## Overview

CSV Sync Service monitors local CSV files for modifications and intelligently syncs them to a remote server. It checks file modification dates and only uploads files that either:
- Don't exist on the server yet
- Have been modified more recently than the server version

## Features

- **Automatic File Detection**: Monitors for modified CSV files based on modification timestamps
- **Smart Synchronization**: Only uploads files that are new or have been updated
- **Server Verification**: Checks if files already exist on the server before uploading
- **Compatible Stack**: Built to work with nginx, PHP 8.3, and MariaDB
- **Reliable**: Python-based script for consistent and predictable behavior

## Requirements

- Python 3.6+
- nginx web server
- PHP 8.3
- MariaDB

## Installation

1. Clone the repository:
```bash
git clone https://github.com/gitgudprint/csv-sync-service.git
cd csv-sync-service
```

2. Install any required Python dependencies (if applicable):
```bash
pip install -r requirements.txt
```

3. Configure your server connection and file paths in the appropriate configuration file

## Usage

Run the synchronization script:
```bash
python sync_service.py
```

## Configuration

Configure the following before running:
- Local CSV file directory path
- Remote server connection details (host, credentials, etc.)
- Sync interval and monitoring preferences

## How It Works

1. **File Monitoring**: The service scans the local directory for CSV files
2. **Date Comparison**: Compares the modification date of local files with server versions
3. **Server Check**: Verifies if the file exists on the remote server
4. **Upload**: If the file is new or has been modified, uploads it to the server
5. **Logging**: Records all sync operations for auditing and troubleshooting

## Architecture

- **Backend**: Python synchronization logic
- **Web Server**: nginx for serving and API endpoints
- **Application**: PHP 8.3 for server-side processing
- **Database**: MariaDB for storing file metadata and sync history

## License

[Add your license information here]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or suggestions, please open an issue on the repository.
