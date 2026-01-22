#!/bin/bash
# restart_and_tail.sh - Start both backend (5010) and frontend (5174) services

echo "=== TRAVELLAND SERVICES STARTUP ==="
echo "Backend: Quart on port 5010"
echo "Frontend: Vite on port 5174"

# Kill any existing processes
echo "Stopping existing services..."
pkill -9 -f "hypercorn\|quart\|vite\|npm.*dev" || true

# Kill any processes using ports 5010 or 5174
for port in 5010 5174; do
    PORT_PIDS=$(ss -ltnp 2>/dev/null | grep ":$port" | grep -o 'pid=[0-9]*' | cut -d'=' -f2 | tr '\n' ' ')
    if [ ! -z "$PORT_PIDS" ]; then
        echo "Force killing processes using port $port: $PORT_PIDS"
        for pid in $PORT_PIDS; do
            kill -9 $pid 2>/dev/null || true
        done
    fi
done

# Wait for ports to be free
echo "Ensuring ports 5010 and 5174 are free..."
for port in 5010 5174; do
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
for port in 5010 5174; do
    if ss -ltn 2>/dev/null | grep -q ":$port"; then
        echo "ERROR: Cannot free port $port. Something is holding it."
        exit 1
    fi
done

echo "Starting backend on port 5010..."
cd /home/markm/TravelLand
hypercorn city_guides.src.app:app --bind 0.0.0.0:5010 &
BACKEND_PID=$!
echo $BACKEND_PID > backend.pid

echo "Starting frontend on port 5174..."
cd /home/markm/TravelLand/frontend
npm run dev &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../frontend.pid

cd /home/markm/TravelLand
echo "Services started:"
echo "  Backend (Quart): http://localhost:5010"
echo "  Frontend (Vite): http://localhost:5174"
echo "PIDs saved to backend.pid and frontend.pid"
