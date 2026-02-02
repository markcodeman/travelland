#!/bin/bash
# docker-dev.sh - Lightweight Docker-based development environment for TravelLand

echo "🚀 Starting TravelLand development environment with Docker..."

# Function to check Docker installation
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker not found. Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ docker-compose not found. Please install Docker Desktop which includes it"
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        echo "❌ Docker daemon is not running. Please start Docker Desktop"
        exit 1
    fi
}

# Function to stop existing containers
stop_existing_containers() {
    echo "🛑 Stopping existing containers..."
    docker-compose down -v 2>/dev/null || true
    echo "✅ Existing containers stopped"
}

# Function to build and start containers
start_containers() {
    echo "📦 Building and starting containers..."
    docker-compose up --build -d
    
    # Wait for services to be ready
    echo "⏳ Waiting for services to be ready..."
    
    # Wait for Redis
    for i in {1..10}; do
        if docker exec travelland-redis redis-cli ping &> /dev/null; then
            echo "✅ Redis is ready"
            break
        fi
        echo "⏳ Waiting for Redis (attempt $i/10)..."
        sleep 2
    done
    
    # Wait for Backend
    for i in {1..15}; do
        if curl -s http://localhost:5010/health &> /dev/null; then
            echo "✅ Backend is ready"
            break
        fi
        echo "⏳ Waiting for Backend (attempt $i/15)..."
        sleep 3
    done
    
    # Wait for Frontends
    echo "⏳ Waiting for frontends to initialize..."
    sleep 10
}

# Function to display startup summary
show_summary() {
    echo ""
    echo "🎉 All services started successfully!"
    echo ""
    echo "📊 Container status:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    echo "📍 Access URLs:"
    echo "   - Backend (Quart): http://localhost:5010"
    echo "   - Health Check: http://localhost:5010/health"
    echo "   - Frontend (React/Vite): http://localhost:5174"
    echo "   - Next.js App: http://localhost:3000"
    echo ""
    echo "📝 To view logs:"
    echo "   - Backend: docker logs -f travelland-backend"
    echo "   - Frontend: docker logs -f travelland-frontend"
    echo "   - Next.js: docker logs -f travelland-nextapp"
    echo "   - Redis: docker logs -f travelland-redis"
    echo ""
    echo "🔧 To stop services:"
    echo "   ./docker-dev.sh stop"
}

# Function to stop services
stop_services() {
    echo "🛑 Stopping TravelLand services..."
    docker-compose down -v
    echo "✅ All services stopped"
    exit 0
}

# Function to view logs
view_logs() {
    if [ "$1" = "backend" ]; then
        docker logs -f travelland-backend
    elif [ "$1" = "frontend" ]; then
        docker logs -f travelland-frontend
    elif [ "$1" = "nextapp" ]; then
        docker logs -f travelland-nextapp
    elif [ "$1" = "redis" ]; then
        docker logs -f travelland-redis
    else
        echo "📝 Displaying all service logs..."
        docker-compose logs -f
    fi
    exit 0
}

# Function to display help
show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start    Start the development environment (default)"
    echo "  stop     Stop all services"
    echo "  logs     View all logs"
    echo "  logs [service]  View specific service logs (backend, frontend, nextapp, redis)"
    echo "  help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start          # Start all services"
    echo "  $0 stop           # Stop all services"
    echo "  $0 logs backend   # View backend logs"
    echo "  $0 logs           # View all logs"
    exit 0
}

# Main script logic
if [ "$1" = "stop" ]; then
    stop_services
elif [ "$1" = "logs" ]; then
    view_logs "$2"
elif [ "$1" = "help" ] || [ "$1" = "--help" ]; then
    show_help
elif [ -n "$1" ]; then
    echo "❌ Unknown command: $1"
    show_help
fi

# Start the services
check_docker
stop_existing_containers
start_containers
show_summary

# Wait for user to press Ctrl+C to stop services
echo ""
echo "💡 Press Ctrl+C to stop all services"
trap stop_services INT TERM

# Keep script running
wait