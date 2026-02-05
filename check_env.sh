#!/bin/bash
# Safe environment check script - Never exposes API keys
# Usage: ./check_env.sh

check_env() {
    local key_name=$1
    local key_value=$2
    
    if [[ -n "$key_value" ]]; then
        # Show only first 6 and last 4 chars, mask the rest
        local masked="${key_value:0:6}****${key_value: -4}"
        echo "✅ $key_name: $masked"
        return 0
    else
        echo "❌ $key_name: NOT SET"
        return 1
    fi
}

# Load environment
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
    echo "Loaded .env file"
else
    echo "⚠️  No .env file found in current directory"
fi

echo ""
echo "🔐 API Key Status:"
echo "=================="

# Check all required keys
check_env "GROQ_API_KEY" "$GROQ_API_KEY"
check_env "GEOAPIFY_API_KEY" "$GEOAPIFY_API_KEY"
check_env "LOCATIONIQ_KEY" "$LOCATIONIQ_KEY"
check_env "MAPILLARY_TOKEN" "$MAPILLARY_TOKEN"
check_env "GEONAMES_USERNAME" "$GEONAMES_USERNAME"
check_env "REDIS_URL" "$REDIS_URL"
check_env "PIXABAY_API_KEY" "$PIXABAY_API_KEY"
check_env "WIKIMEDIA_ACCESS_TOKEN" "$WIKIMEDIA_ACCESS_TOKEN"

echo ""
echo "💡 To add a new key:"
echo "   echo 'KEY_NAME=value' >> .env"
