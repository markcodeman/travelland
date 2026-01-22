#!/bin/bash
# Test /search endpoint with various city names and print results

API_URL="http://localhost:5010/search"

# Test with problematic city name
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"city": "City of London, United Kingdom", "category": "restaurant"}'
echo -e "\n---\n"

# Test with normalized city name
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"city": "London", "category": "restaurant"}'
echo -e "\n---\n"

# Test with another well-known city
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"city": "Berlin", "category": "restaurant"}'
echo -e "\n---\n"

# Test with a city that should return no results
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"city": "Atlantis", "category": "restaurant"}'
echo -e "\n---\n"
