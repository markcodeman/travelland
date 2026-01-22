import asyncio
import sys
import os
sys.path.insert(0, '/home/markm/TravelLand/city_guides/src')

from semantic import search_and_reason, analyze_any_query

async def test_api_call():
    try:
        q = "tell me about coffee in London"
        print(f"Analyzing query: {q}")
        analysis = analyze_any_query(q, [], "")  # Empty venues and history
        print(f"Analysis result: {analysis}")

        # Test with some mock coffee venues
        mock_venues = [
            {"name": "Starbucks", "type": "coffee", "lat": 51.5, "lon": -0.1},
            {"name": "Costa Coffee", "type": "coffee", "lat": 51.5, "lon": -0.1}
        ]
        analysis_with_venues = analyze_any_query(q, mock_venues, "")
        print(f"Analysis result with venues: {analysis_with_venues}")

        # Simulate the API call parameters
        city = "London"
        mode = "explorer"
        venues = mock_venues  # Use mock venues
        weather = None
        neighborhoods = []
        session = None  # aiohttp_session might be None
        wikivoyage = None
        history_str = ""

        print("Calling search_and_reason with mock venues...")
        result = await search_and_reason(q, city, mode, context_venues=venues, weather=weather, neighborhoods=neighborhoods, session=session, wikivoyage=wikivoyage, history=history_str)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_call())