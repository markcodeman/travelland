# Test ContextualWebSearch API endpoint
# Replace YOUR_API_KEY with your actual key

import requests

API_KEY = "YOUR_API_KEY"
ENDPOINT = "https://contextualwebsearch.com/websearch"

params = {
    "q": "Tlaquepaque Jalisco travel",
    "pageNumber": 1,
    "pageSize": 5,
    "autoCorrect": True
}
headers = {
    "X-RapidAPI-Key": API_KEY,  # Use this if you signed up via RapidAPI
    # If you have a direct key, check their docs for the correct header
}

try:
    response = requests.get(ENDPOINT, params=params, headers=headers, timeout=15)
    print("Status:", response.status_code)
    print("Response:", response.json())
except Exception as e:
    print("Error:", e)
