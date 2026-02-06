#!/usr/bin/env python3
"""Test London Historic Sites search and report quality"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from city_guides.src.persistence import _search_impl

async def test_london_historic():
    """Test historic sites search for London"""
    print("=" * 60)
    print("TESTING: Historic Sites in London")
    print("=" * 60)
    
    result = _search_impl("London", "historic")
    
    venues = result.get("venues", [])
    print(f"\nFound {len(venues)} venues\n")
    
    if venues:
        print("Venue Results:")
        print("-" * 60)
        for i, venue in enumerate(venues[:10], 1):
            name = venue.get("name", "Unknown")
            address = venue.get("address", "No address")
            description = venue.get("description", "No description")
            tags = venue.get("tags", {})
            
            print(f"\n{i}. {name}")
            print(f"   Address: {address}")
            print(f"   Description: {description[:100]}..." if len(description) > 100 else f"   Description: {description}")
            if tags:
                print(f"   Tags: {str(tags)[:100]}")
    else:
        print("NO VENUES FOUND")
        print(f"Debug info: {result.get('debug_info', {})}")
    
    # Check for garbage venues
    garbage_indicators = ["employment", "office", "government", "administration", "clinic", "hospital"]
    garbage_found = []
    
    for venue in venues:
        name = venue.get("name", "").lower()
        tags_str = str(venue.get("tags", {})).lower()
        
        for indicator in garbage_indicators:
            if indicator in name or indicator in tags_str:
                garbage_found.append((venue.get("name"), indicator))
                break
    
    print("\n" + "=" * 60)
    print("QUALITY CHECK:")
    print("=" * 60)
    
    if garbage_found:
        print(f"\n❌ FOUND {len(garbage_found)} GARBAGE VENUES:")
        for name, indicator in garbage_found:
            print(f"   - {name} (matched: {indicator})")
    else:
        print("\n✅ No garbage venues found!")
    
    # Check for UI issues
    print("\n" + "=" * 60)
    print("UI CHECK:")
    print("=" * 60)
    
    for venue in venues[:3]:
        name = venue.get("name", "")
        tags = venue.get("tags", {})
        
        # Check if name would display as individual letters (if tags is a string)
        if isinstance(tags, str):
            print(f"❌ Venue '{name}' has tags as string: '{tags}'")
            print(f"   This would cause UI bug - letters displayed individually!")
        else:
            print(f"✅ Venue '{name}' has proper tags type: {type(tags).__name__}")
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)
    print(f"Total venues: {len(venues)}")
    print(f"Garbage venues: {len(garbage_found)}")
    print(f"Quality score: {max(0, 100 - len(garbage_found) * 20)}%")
    
    return result

if __name__ == "__main__":
    asyncio.run(test_london_historic())
