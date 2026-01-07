#!/bin/bash

# Define the Flask app process name or path
FLASK_APP="/home/markm/TravelLand/city-guides/app.py"

# Ensure the virtual environment exists
if [ ! -d "/home/markm/TravelLand/city-guides/.venv" ]; then
  echo "Virtual environment not found. Creating one..."
  python3 -m venv /home/markm/TravelLand/city-guides/.venv
  echo "Virtual environment created. Installing dependencies..."
  source /home/markm/TravelLand/city-guides/.venv/bin/activate
  pip install -r /home/markm/TravelLand/city-guides/requirements.txt
else
  echo "Virtual environment found."
fi

# Find and kill all Flask processes
FLASK_PROCESSES=$(pgrep -f "app.py")
if [ ! -z "$FLASK_PROCESSES" ]; then
  echo "Stopping all Flask processes (PIDs: $FLASK_PROCESSES)..."
  kill -9 $FLASK_PROCESSES
else
  echo "No Flask processes found."
fi

# Activate the virtual environment
source /home/markm/TravelLand/city-guides/.venv/bin/activate

# Ensure the log file is created and writable
LOG_FILE="/home/markm/TravelLand/city-guides/scripts/flask_app.log"
touch $LOG_FILE
chmod 644 $LOG_FILE

# Restart the Flask app
nohup python3 $FLASK_APP > $LOG_FILE 2>&1 &
FLASK_PID=$!
echo "Flask app restarted with PID: $FLASK_PID."

# Verify the app is running
sleep 2
if ps -p $FLASK_PID > /dev/null; then
  echo "Flask app is running successfully."
else
  echo "Failed to start Flask app. Check the log file for details: $LOG_FILE"
fi