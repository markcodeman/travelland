import asyncio
from city_guides.src import semantic

async def run():
    # Simulate a frustrated conversation history
    history = "User: I want coffee recommendations\nMarco: I'm ready to explore\nUser: Any specific coffee shops? You're not listening"
    q = "Any specific coffee shops?"
    city = "London"
    # Provide no context_venues to force fallback to local data or enrichment
    resp = await semantic.search_and_reason(q, city=city, mode='explorer', context_venues=[], weather=None, neighborhoods=None, session=None, wikivoyage=None, history=history)
    print('--- FINAL RESPONSE ---')
    print(resp)

if __name__ == '__main__':
    asyncio.run(run())
