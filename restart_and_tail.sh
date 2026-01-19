#!/bin/bash
# restart_and_tail.sh - Restart Quart/Hypercorn app and tail logs

# Kill any running app server processes
pkill -f app.py || pkill -f hypercorn || pkill -f quart || pkill -f python3 || true

# Start the app in the background, output to app.log
nohup /home/markm/TravelLand/venv/bin/python city_guides/app.py > app.log 2>&1 &

# Wait a moment for the app to start
sleep 2

echo "--- App restarted. Launching browser and tailing logs (Ctrl+C to stop) ---"
# Launch the default browser to the app URL (Linux: xdg-open, Mac: open)
if command -v xdg-open > /dev/null; then
	xdg-open http://127.0.0.1:5010 &
elif command -v open > /dev/null; then
	open http://127.0.0.1:5010 &
else
	echo "Please open http://127.0.0.1:5010 in your browser."
fi
tail -f app.log
