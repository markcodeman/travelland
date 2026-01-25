#!/bin/bash
# restart_and_tail.sh - Start both backend (5010) and frontend (5174) services

echo "=== TRAVELLAND SERVICES STARTUP ==="
echo "Backend: Quart on port 5010"
echo "Frontend: Vite on port 5174"
echo "Next.js: Next app on port 3000"


# Kill any existing processes
echo "Stopping existing services..."
pkill -9 -f "hypercorn\|quart\|vite\|npm.*dev\|next dev" || true

# Kill any processes using ports 5010, 5174, or 3000
for port in 5010 5174 3000; do
    PORT_PIDS=$(ss -ltnp 2>/dev/null | grep ":$port" | grep -o 'pid=[0-9]*' | cut -d'=' -f2 | tr '\n' ' ')
    if [ ! -z "$PORT_PIDS" ]; then
        echo "Force killing processes using port $port: $PORT_PIDS"
        for pid in $PORT_PIDS; do
            kill -9 $pid 2>/dev/null || true
        done
    fi
done

# Wait for ports to be free
echo "Ensuring ports 5010, 5174, and 3000 are free..."
for port in 5010 5174 3000; do
    for i in {1..5}; do
        if ! ss -ltn 2>/dev/null | grep -q ":$port"; then
            echo "Port $port is free"
            break
        fi
        echo "Waiting for port $port to free up (attempt $i/5)..."
        sleep 1
    done
done

# Final check - exit if ports still in use
for port in 5010 5174 3000; do
    if ss -ltn 2>/dev/null | grep -q ":$port"; then
        echo "ERROR: Cannot free port $port. Something is holding it."
        exit 1
    fi
done




echo "Exporting environment variables from .env (robust)..."
cd /home/markm/TravelLand
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "Starting backend on port 5010 (using venv Python/hypercorn)..."
# Use venv hypercorn if available, else fallback
if [ -x "./venv/bin/hypercorn" ]; then
    ./venv/bin/hypercorn city_guides.src.app:app --bind 0.0.0.0:5010 &
elif [ -x "./venv/bin/python" ]; then
    ./venv/bin/python -m hypercorn city_guides.src.app:app --bind 0.0.0.0:5010 &
else
    hypercorn city_guides.src.app:app --bind 0.0.0.0:5010 &
fi
BACKEND_PID=$!
echo $BACKEND_PID > backend.pid

echo "Starting frontend on port 5174..."
cd /home/markm/TravelLand/frontend
npm run dev &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../frontend.pid

echo "Starting Next.js app on port 3000..."
cd /home/markm/TravelLand/next-app
npm run dev &
NEXT_PID=$!
echo $NEXT_PID > ../next.pid

cd /home/markm/TravelLand
echo "Services started:"
echo "  Backend (Quart): http://localhost:5010"
echo "  Frontend (Vite): http://localhost:5174"
echo "PIDs saved to backend.pid and frontend.pid"
echo "  Next.js (Next): http://localhost:3000"
echo "PIDs saved to backend.pid, frontend.pid, and next.pid"
