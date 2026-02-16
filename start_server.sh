#!/bin/bash
# start_server.sh - Production server startup script for TravelLand on Render

echo "🚀 Starting TravelLand production server..."

# Set working directory to the app root
cd /opt/render/project/src || cd /app || cd .

# Export environment variables from .env if it exists
if [ -f .env ]; then
    echo "📄 Loading environment variables from .env"
    export $(grep -v '^#' .env | xargs)
fi

# Set production environment
export QUART_ENV=production
export QUART_DEBUG=false

# Start the Quart application with Hypercorn
echo "📡 Starting backend server on port 10000..."
exec hypercorn city_guides.src.app:app --bind 0.0.0.0:10000 --workers 1