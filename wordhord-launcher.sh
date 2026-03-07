#!/bin/bash
# Wordhord Application Launcher
# This script handles launching the Wordhord application

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the Wordhord directory
cd "$SCRIPT_DIR" || exit 1

# Check if required commands exist
check_requirements() {
  local missing=""
  
  if ! command -v node &> /dev/null; then
    missing="$missing\n  - Node.js"
  fi
  
  if ! command -v python3 &> /dev/null; then
    missing="$missing\n  - Python 3"
  fi
  
  if [ -n "$missing" ]; then
    notify-send "Wordhord - Missing Dependencies" "The following are required:$missing" -u critical
    exit 1
  fi
}

# Show notification that app is starting
notify-send "Wordhord" "Starting vocabulary trainer..." -i wordhord -t 3000

# Check requirements
check_requirements

# Run the start script
bash start.sh

# If start.sh exits with error, show notification
if [ $? -ne 0 ]; then
  notify-send "Wordhord - Error" "Failed to start application. Check the terminal for details." -u critical
fi
