#!/bin/bash

# Define the Flask app process name or path
FLASK_APP_DIR="/home/markm/TravelLand/city_guides"
FLASK_MODULE="src.app"

# Use the main project venv where dependencies are installed
VENV_PATH="/home/markm/TravelLand/venv"
if [ ! -d "$VENV_PATH" ]; then
  echo "Virtual environment not found at $VENV_PATH"
  exit 1
fi

# Find and kill all Flask processes
FLASK_PROCESSES=$(pgrep -f "src.app")
if [ ! -z "$FLASK_PROCESSES" ]; then
  echo "Stopping all Flask processes (PIDs: $FLASK_PROCESSES)..."
  kill -9 $FLASK_PROCESSES
else
  echo "No Flask processes found."
fi

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Ensure the log file is created and writable
LOG_FILE="/home/markm/TravelLand/city_guides/scripts/flask_app.log"
touch $LOG_FILE
chmod 644 $LOG_FILE

# Restart the Flask app
cd $FLASK_APP_DIR
PYTHONPATH="/home/markm/TravelLand" nohup python3 -m $FLASK_MODULE > $LOG_FILE 2>&1 &
FLASK_PID=$!
echo "Flask app restarted with PID: $FLASK_PID."

# Verify the app is running
sleep 2
if ps -p $FLASK_PID > /dev/null; then
  echo "Flask app is running successfully."
else
  echo "Failed to start Flask app. Check the log file for details: $LOG_FILE"
fi