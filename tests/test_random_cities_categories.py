import asyncio
import sys
sys.path.insert(0, '/home/markcodeman/CascadeProjects/travelland')
from city_guides.src.simple_categories import get_dynamic_categories
import random

# List of 50 random cities from around the world
RANDOM_CITIES = [
    ("Cape Town", "", "South Africa"),
    ("Bangkok", "", "Thailand"),
    ("Lisbon", "", "Portugal"),
    ("Seoul", "", "South Korea"),
    ("Buenos Aires", "", "Argentina"),
    ("Cairo", "", "Egypt"),
    ("Amsterdam", "", "Netherlands"),
    ("Berlin", "", "Germany"),
    ("Toronto", "", "Canada"),
    ("Sydney", "", "Australia"),
    ("Mumbai", "", "India"),
    ("Singapore", "", "Singapore"),
    ("Hong Kong", "", "China"),
    ("San Francisco", "CA", "USA"),
    ("Chicago", "IL", "USA"),
    ("Boston", "MA", "USA"),
    ("Washington, D.C.", "", "USA"),
    ("Miami", "FL", "USA"),
    ("Las Vegas", "NV", "USA"),
    ("Austin", "TX", "USA"),
    ("Seattle", "WA", "USA"),
    ("Denver", "CO", "USA"),
    ("Phoenix", "AZ", "USA"),
    ("Portland", "OR", "USA"),
    ("Salt Lake City", "UT", "USA"),
    ("San Diego", "CA", "USA"),
    ("New Orleans", "LA", "USA"),
    ("Philadelphia", "PA", "USA"),
    ("Pittsburgh", "PA", "USA"),
    ("Detroit", "MI", "USA"),
    ("Cleveland", "OH", "USA"),
    ("Indianapolis", "IN", "USA"),
    ("Columbus", "OH", "USA"),
    ("Nashville", "TN", "USA"),
    ("Atlanta", "GA", "USA"),
    ("Charlotte", "NC", "USA"),
    ("Raleigh", "NC", "USA"),
    ("Durham", "NC", "USA"),
    ("Charleston", "SC", "USA"),
    ("Savannah", "GA", "USA"),
    ("Newport", "RI", "USA"),
    ("Providence", "RI", "USA"),
    ("Portland", "ME", "USA"),
    ("Bangor", "ME", "USA"),
    ("Fargo", "ND", "USA"),
    ("Bismarck", "ND", "USA"),
    ("Sioux Falls", "SD", "USA"),
    ("Cheyenne", "WY", "USA"),
    ("Casper", "WY", "USA")
]

async def test_random_cities():
    print("Testing 50 random cities for dynamic categories...\n")
    
    # Shuffle cities to randomize testing order
    random.shuffle(RANDOM_CITIES)
    
    generic_category_count = 0
    zero_category_count = 0
    total_categories = 0
    unique_categories = set()
    
    for i, (city, state, country) in enumerate(RANDOM_CITIES, 1):
        try:
            print(f"{i}/50: Testing {city}, {state} {country}")
            categories = await get_dynamic_categories(city, state, country)
            
            if len(categories) == 0:
                zero_category_count += 1
                print(f"⚠️  WARNING: 0 categories found for {city}")
                
            for cat in categories:
                total_categories += 1
                unique_categories.add(cat['label'])
                
                # Check for generic categories
                if cat['label'] in ['Art & Culture', 'Parks & Nature', 'Food & Dining', 'Shopping', 'Nightlife', 'Historic Sites', 'Education', 'Theatre & Shows', 'Sports']:
                    generic_category_count += 1
                
            print(f"   Found {len(categories)} categories")
            
        except Exception as e:
            print(f"   Error: {e}")
    
    # Results summary
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    print(f"Total cities tested: {len(RANDOM_CITIES)}")
    print(f"Total categories found: {total_categories}")
    print(f"Average categories per city: {total_categories / len(RANDOM_CITIES):.1f}")
    print(f"Unique categories: {len(unique_categories)}")
    print(f"Generic categories found: {generic_category_count}")
    print(f"Cities with 0 categories: {zero_category_count}")
    print("\nTop 20 unique categories:")
    for cat in sorted(list(unique_categories))[:20]:
        print(f"  - {cat}")
    
    # Check performance
    print("\n" + "="*60)
    print("CATEGORY PERFORMANCE ANALYSIS")
    print("="*60)
    if zero_category_count > 0:
        print(f"⚠️  {zero_category_count} cities have no categories (requires attention)")
    
    if generic_category_count > total_categories * 0.6:
        print("⚠️  High percentage of generic categories (needs improvement)")
    elif generic_category_count > total_categories * 0.4:
        print("⚠️  Moderate percentage of generic categories (could be improved)")
    else:
        print("✅  Low percentage of generic categories (good)")
    
    if len(unique_categories) < 80:
        print("⚠️  Limited category diversity (needs improvement)")
    else:
        print("✅  Good category diversity")
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    if zero_category_count > 0:
        print("1. Add fun facts and category mappings for cities with 0 categories")
    if generic_category_count > total_categories * 0.4:
        print("2. Enhance city-specific category mappings")
    if len(unique_categories) < 80:
        print("3. Add more distinctive categories for major cities")

if __name__ == "__main__":
    asyncio.run(test_random_cities())