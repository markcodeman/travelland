#!/bin/bash
# dev.sh - Comprehensive development environment startup script for TravelLand
# Merged from dev-fast.sh and restart_and_tail.sh with best features from both

echo "🚀 Starting TravelLand development environment..."

# Function to kill existing processes
kill_existing_services() {
    echo "🛑 Stopping existing services..."
    pkill -9 -f "hypercorn\|quart\|vite\|npm.*dev\|next dev" 2>/dev/null || true
    
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
    echo "⏳ Ensuring ports 5010, 5174, and 3000 are free..."
    for port in 5010 5174 3000; do
        for i in {1..5}; do
            if ! ss -ltn 2>/dev/null | grep -q ":$port"; then
                echo "✅ Port $port is free"
                break
            fi
            echo "⏳ Waiting for port $port to free up (attempt $i/5)..."
            sleep 1
        done
    done
    
    # Final check - exit if ports still in use
    for port in 5010 5174 3000; do
        if ss -ltn 2>/dev/null | grep -q ":$port"; then
            echo "❌ ERROR: Cannot free port $port. Something is holding it."
            exit 1
        fi
    done
}

# Function to start backend service
start_backend() {
    echo "📡 Starting City Guides backend on port 5010..."
    cd /home/markcodeman/CascadeProjects/travelland
    
    # Export environment variables from .env, skip keys with dashes (e.g., RapidAPI keys)
    if [ -f .env ]; then
        export $(grep -v '^#' .env | grep -v '-' | xargs)
    fi
    
    # Use venv hypercorn if available, else fallback
    if [ -x "./.venv/bin/hypercorn" ]; then
        ./.venv/bin/hypercorn city_guides.src.app:app --reload --bind 0.0.0.0:5010 &
    elif [ -x "./.venv/bin/python" ]; then
        ./.venv/bin/python -m hypercorn city_guides.src.app:app --reload --bind 0.0.0.0:5010 &
    else
        hypercorn city_guides.src.app:app --reload --bind 0.0.0.0:5010 &
    fi
    BACKEND_PID=$!
    echo $BACKEND_PID > backend.pid
    echo "✅ Backend started with PID $BACKEND_PID"
}

# Function to start frontend service
start_frontend() {
    echo "🎨 Starting React frontend on port 5174..."
    cd /home/markcodeman/CascadeProjects/travelland/frontend
    npm run dev -- --port 5174 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../frontend.pid
    echo "✅ Frontend started with PID $FRONTEND_PID"
}

# Function to start Next.js service
start_nextjs() {
    echo "⚡ Starting Next.js app on port 3000..."
    cd /home/markcodeman/CascadeProjects/travelland/next-app
    TURBOPACK_ROOT=./next-app npm run dev -- --port 3000 &
    NEXT_PID=$!
    echo $NEXT_PID > ../next.pid
    echo "✅ Next.js started with PID $NEXT_PID"
}

# Function to display startup summary
show_summary() {
    echo ""
    echo "🎉 All services started successfully!"
    echo "📍 Backend (Quart): http://localhost:5010"
    echo "🎨 Frontend (Vite): http://localhost:5174"
    echo "⚡ Next.js: http://localhost:3000"
    echo ""
    echo "📁 PIDs saved to:"
    echo "   - backend.pid ($BACKEND_PID)"
    echo "   - frontend.pid ($FRONTEND_PID)"
    echo "   - next.pid ($NEXT_PID)"
    echo ""
    echo "💡 Press Ctrl+C to stop all services"
}

# Function to handle cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping all services..."
    if [ -f backend.pid ]; then
        kill $(cat backend.pid) 2>/dev/null || true
        rm backend.pid
    fi
    if [ -f frontend.pid ]; then
        kill $(cat frontend.pid) 2>/dev/null || true
        rm frontend.pid
    fi
    if [ -f next.pid ]; then
        kill $(cat next.pid) 2>/dev/null || true
        rm next.pid
    fi
    echo "✅ All services stopped"
    exit 0
}

# Set up signal handlers for clean shutdown
trap cleanup INT TERM

# Main execution
kill_existing_services
start_backend
start_frontend
start_nextjs
show_summary

# Wait for interrupt to trigger cleanup
wait