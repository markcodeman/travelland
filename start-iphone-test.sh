#!/bin/bash
# Quick start script to instantly test apps on iPhone

echo "=================================================="
echo "🚀 Travelland - Instant iPhone Testing"
echo "=================================================="
echo ""
echo "Which app do you want to test on your iPhone?"
echo ""
echo "1) City Guides (port 5010)"
echo "2) Hotel Finder (port 5000)"
echo "3) Both apps"
echo ""
read -p "Enter choice (1-3): " choice

start_city_guides() {
    echo ""
    echo "🏙️  Starting City Guides..."
    cd city-guides
    pip install -q -r requirements.txt
    python app.py &
    APP_PID=$!
    sleep 3
    echo "✅ City Guides running on port 5010"
    echo ""
    echo "📱 Creating public URL for iPhone..."
    npx -y localtunnel --port 5010
}

start_hotel_finder() {
    echo ""
    echo "🏨 Starting Hotel Finder..."
    cd hotel-finder
    pip install -q -r requirements.txt
    python app.py &
    APP_PID=$!
    sleep 3
    echo "✅ Hotel Finder running on port 5000"
    echo ""
    echo "📱 Creating public URL for iPhone..."
    npx -y localtunnel --port 5000
}

case $choice in
    1)
        start_city_guides
        ;;
    2)
        start_hotel_finder
        ;;
    3)
        echo ""
        echo "🚀 Starting both apps..."
        echo ""
        echo "City Guides will run in background."
        echo "Open http://localhost:5010 for City Guides"
        echo "Open http://localhost:5000 for Hotel Finder"
        echo ""
        cd city-guides
        pip install -q -r requirements.txt
        python app.py &
        cd ../hotel-finder
        pip install -q -r requirements.txt
        python app.py &
        sleep 3
        echo ""
        echo "✅ Both apps running!"
        echo ""
        echo "📱 Now run in separate terminals:"
        echo "   npx localtunnel --port 5010  # For City Guides"
        echo "   npx localtunnel --port 5000  # For Hotel Finder"
        echo ""
        echo "Press Ctrl+C to stop..."
        wait
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
