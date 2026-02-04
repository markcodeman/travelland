import asyncio
import sys
import logging
import json
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from city_guides.src.semantic import semantic
except ImportError as e:
    print(f"IMPORT ERROR: Install deps: pip install duckduckgo-search wikipedia-api wikivy aiohttp redis")
    print(f"Error: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run():
    history = [
        {"role": "user", "content": "Recommend itinerary for 3 days in London?"},
        {"role": "assistant", "content": "Day 1: Big Ben, Thames..."}
    ]
    
    # Test 1: Basic query analysis
    q = "What are fun facts about London?"
    city = "London"
    try:
        # Use semantic module functions directly since it's a dict interface
        analysis = semantic['analyze_any_query'](q, [], history)
        logger.info(f'Query analysis: {analysis}')
        
        # Build response context
        context = {
            'venues': [],
            'city': city,
            'neighborhoods': [],
            'weather': None,
            'session': None,
            'wikivoyage': None,
            'history': history
        }
        
        response = semantic['build_response_for_any_query'](q, context, analysis)
        logger.info('RESPONSE 1')
        logger.info(response)
    except Exception as e:
        logger.error(f"Test 1 failed: {e}")

    # Test 2: Enhanced async functions
    try:
        logger.info('Testing enhanced async functions...')
        categories = await semantic['get_city_categories'](city)
        logger.info(f'Categories: {categories}')
        
        facts = await semantic['get_fun_facts'](city)
        logger.info(f'Fun facts: {facts[:2]}')
        
        guide = await semantic['get_city_guide'](city)
        logger.info(f'Guide: {guide}')
        
        enhanced_response = await semantic['enhanced_search_and_reason'](q, city, mode='explorer')
        logger.info('ENHANCED RESPONSE')
        logger.info(json.dumps(enhanced_response, indent=2))
    except Exception as e:
        logger.error(f"Enhanced test failed: {e}")

    # Test 3: Specific venue request
    q = "Any specific coffee shops? You're not listening"
    try:
        analysis = semantic['analyze_any_query'](q, [], history)
        logger.info(f'Venue request analysis: {analysis}')
        
        context = {
            'venues': [],
            'city': city,
            'neighborhoods': [],
            'weather': None,
            'session': None,
            'wikivoyage': None,
            'history': history
        }
        
        response = semantic['build_response_for_any_query'](q, context, analysis)
        logger.info('FINAL RESPONSE (Coffee Shops)')
        logger.info(response)
        
        # Test enhanced coffee shop search
        enhanced_coffee = await semantic['enhanced_search_and_reason'](q, city, mode='explorer')
        logger.info('ENHANCED COFFEE RESPONSE')
        logger.info(json.dumps(enhanced_coffee, indent=2))
    except Exception as e:
        logger.error(f"Test 3 failed: {e}")

if __name__ == '__main__':
    asyncio.run(run())
