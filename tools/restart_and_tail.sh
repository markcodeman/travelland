#!/bin/bash
# restart_and_tail.sh - Restart Quart/Hypercorn app and tail logs

# Kill any running app server processes
pkill -f app.py || pkill -f hypercorn || pkill -f quart || pkill -f python3 || true
pkill -f "vite\|npm" || true

# Start the app in the background, output to app.log
cd /home/markm/TravelLand
nohup /home/markm/TravelLand/venv/bin/python -m city_guides.src.app > app.log 2>&1 &

# Start the frontend dev server in the background
cd /home/markm/TravelLand/frontend
nohup /home/markm/.nvm/versions/node/v24.13.0/bin/npm run dev > frontend.log 2>&1 &
cd /home/markm/TravelLand

# Start the port monitor in the background
cd /home/markm/TravelLand/city_guides/scripts
nohup python3 port_monitor.py --ports 5010 5174 --interval 5 > port_monitor.log 2>&1 &
cd /home/markm/TravelLand

# Wait a moment for the app to start
sleep 2

echo "--- App restarted. Launching browser and tailing logs (Ctrl+C to stop) ---"
# Launch the default browser to the app URL (Linux: xdg-open, Mac: open)
if command -v xdg-open > /dev/null; then
	xdg-open http://127.0.0.1:5174 &
elif command -v open > /dev/null; then
	open http://127.0.0.1:5174 &
else
	echo "Please open http://127.0.0.1:5010 in your browser."
fi
tail -f app.log
