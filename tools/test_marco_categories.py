#!/usr/bin/env python3
"""
Test script to verify all Marco Chat categories work correctly.
Tests category detection, venue fetching, and RAG fallback behavior.
"""

import requests
import json
from typing import Dict, List, Tuple, Optional

BASE_URL = "http://localhost:5010"

# All categories defined in MarcoChat.jsx
CATEGORIES = {
    # Standard venue categories
    "cafes": ["coffee", "cafe", "espresso"],
    "restaurants": ["restaurant", "food", "dining", "eat"],
    "museums": ["museum", "art gallery", "exhibition"],
    "nightlife": ["nightlife", "bar", "club", "pub"],
    "parks": ["park", "garden", "nature"],
    "hotels": ["hotel", "stay", "accommodation"],
    "entertainment": ["theatre", "theater", "show", "performance", "play", "concert"],
    "castles_und_fortifications": ["castle", "fortification", "fortress", "palace"],
    "historic": ["historic site", "historic landmark", "ancient"],

    # Heritage categories
    "literary_heritage": ["literary", "writer", "author", "book"],
    "music_heritage": ["music", "musical", "jazz", "concert hall"],
    "industrial_heritage": ["industrial", "factory", "mill", "manufacturing"],

    # RAG-only categories (informational)
    "heritage": ["heritage"],
    "maritime": ["maritime"],
    "history": ["history"],
    "architecture": ["architecture"],
}

TEST_CITY = "Barcelona"
TEST_NEIGHBORHOOD = "Barceloneta"

def test_search_endpoint(category: str, city: str = TEST_CITY, neighborhood: Optional[str] = None) -> Dict:
    """Test the /search endpoint with a category."""
    try:
        payload = {
            "query": city,
            "category": category,
            "neighborhood": neighborhood,
            "limit": 5
        }
        resp = requests.post(f"{BASE_URL}/search", json=payload, timeout=30)
        return {
            "status_code": resp.status_code,
            "venues_found": len(resp.json().get("venues", [])),
            "has_quick_guide": bool(resp.json().get("quick_guide")),
            "source": resp.json().get("source", "unknown"),
            "error": resp.json().get("error")
        }
    except Exception as e:
        return {"error": str(e)}

def test_rag_endpoint(query: str, city: str = TEST_CITY, neighborhood: Optional[str] = None) -> Dict:
    """Test the RAG chat endpoint."""
    try:
        payload = {
            "query": query,
            "city": city,
            "neighborhood": neighborhood,
            "venues": [],
            "history": [],
            "max_results": 5
        }
        resp = requests.post(f"{BASE_URL}/api/chat/rag", json=payload, timeout=30)
        data = resp.json()
        return {
            "status_code": resp.status_code,
            "has_answer": bool(data.get("answer") or data.get("response")),
            "answer_length": len(data.get("answer") or data.get("response") or ""),
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    print("=" * 100)
    print("MARCO CHAT CATEGORY TEST REPORT")
    print("=" * 100)
    print(f"\nTest City: {TEST_CITY}")
    print(f"Test Neighborhood: {TEST_NEIGHBORHOOD}")
    print(f"Base URL: {BASE_URL}")
    print("\n" + "=" * 100)

    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/", timeout=5)
    except:
        print(f"\n⚠️  WARNING: Server not running at {BASE_URL}")
        print("Please start the server with: python city_guides/src/app.py")
        return

    results = []

    print("\n📊 CATEGORY TEST RESULTS\n")
    print(f"{'Category':<30} {'Keywords':<30} {'Endpoint':<15} {'Status':<10} {'Venues':<10} {'Quick Guide':<12} {'Notes'}")
    print("-" * 140)

    for category, keywords in CATEGORIES.items():
        # Determine if this is a venue or RAG category
        venue_categories = [
            'cafes', 'restaurants', 'museums', 'nightlife', 'parks', 'hotels',
            'entertainment', 'castles_und_fortifications', 'historic',
            'literary_heritage', 'music_heritage', 'industrial_heritage'
        ]

        is_venue = category in venue_categories

        if is_venue:
            # Test search endpoint
            result = test_search_endpoint(category)
            endpoint = "/search"

            status = "✅" if result.get("status_code") == 200 else "❌"
            venues = result.get("venues_found", 0)
            guide = "Yes" if result.get("has_quick_guide") else "No"

            if result.get("error"):
                notes = f"Error: {result['error'][:40]}"
            elif venues == 0:
                notes = "No venues found - will fallback to RAG"
            else:
                notes = f"Source: {result.get('source', 'unknown')}"

            print(f"{category:<30} {', '.join(keywords[:2]):<30} {endpoint:<15} {status:<10} {venues:<10} {guide:<12} {notes}")

            results.append({
                "category": category,
                "type": "venue",
                "endpoint": endpoint,
                "status": "pass" if result.get("status_code") == 200 else "fail",
                "venues": venues,
                "has_guide": result.get("has_quick_guide"),
                "notes": notes
            })
        else:
            # Test RAG endpoint
            query = f"Tell me about {keywords[0]} in {TEST_CITY}"
            result = test_rag_endpoint(query)
            endpoint = "/api/chat/rag"

            status = "✅" if result.get("status_code") == 200 and result.get("has_answer") else "❌"
            venues = "N/A"
            guide = "N/A"

            if result.get("error"):
                notes = f"Error: {result['error'][:40]}"
            else:
                notes = f"RAG response: {result.get('answer_length', 0)} chars"

            print(f"{category:<30} {', '.join(keywords[:2]):<30} {endpoint:<15} {status:<10} {venues:<10} {guide:<12} {notes}")

            results.append({
                "category": category,
                "type": "rag",
                "endpoint": endpoint,
                "status": "pass" if result.get("status_code") == 200 else "fail",
                "has_answer": result.get("has_answer"),
                "notes": notes
            })

    # Summary
    print("\n" + "=" * 100)
    print("📈 SUMMARY")
    print("=" * 100)

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = total - passed

    venue_cats = [r for r in results if r["type"] == "venue"]
    rag_cats = [r for r in results if r["type"] == "rag"]

    print(f"\nTotal Categories Tested: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")

    print(f"\nVenue Categories: {len(venue_cats)}")
    venue_with_results = sum(1 for r in venue_cats if r.get("venues", 0) > 0)
    print(f"  - With venues found: {venue_with_results}")
    print(f"  - Fallback to RAG: {len(venue_cats) - venue_with_results}")

    print(f"\nRAG-Only Categories: {len(rag_cats)}")
    rag_working = sum(1 for r in rag_cats if r.get("has_answer"))
    print(f"  - With answers: {rag_working}")

    print("\n" + "=" * 100)
    print("🔧 RECOMMENDATIONS")
    print("=" * 100)

    # Categories with no venues
    no_venue_cats = [r["category"] for r in venue_cats if r.get("venues", 0) == 0]
    if no_venue_cats:
        print(f"\n⚠️  Categories with no venue results (will use RAG fallback):")
        for cat in no_venue_cats:
            print(f"   - {cat}")

    # Failed categories
    failed_cats = [r["category"] for r in results if r["status"] == "fail"]
    if failed_cats:
        print(f"\n❌ Failed categories (need attention):")
        for cat in failed_cats:
            print(f"   - {cat}")

    print("\n" + "=" * 100)

if __name__ == "__main__":
    main()
