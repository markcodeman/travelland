import asyncio
import os

# Ensure environment loads the .env file used by semantic.py at import time
# semantic.py already loads .env from project paths

from city_guides.src import semantic

async def run_test():
    q = "Recommend three coffee shops in London with dark roast options and why"
    city = "London"
    mode = "explorer"
    # Provide an empty list of venues to force AI reasoning
    try:
        print("Calling semantic.search_and_reason()...\n")
        res = await semantic.search_and_reason(q, city=city, mode=mode, context_venues=[], weather=None, neighborhoods=None, session=None, wikivoyage=None, history=None)
        print("--- RESULT ---")
        print(res)
    except Exception as e:
        print("Exception during test:", e)

if __name__ == '__main__':
    asyncio.run(run_test())
