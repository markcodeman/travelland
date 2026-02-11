"""Smart neighborhood suggestions for large cities - uses Nominatim + Overpass"""
from typing import List, Dict, Optional
import aiohttp
import asyncio

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Cities that should ONLY use curated data (no Overpass fallback)
CURATED_ONLY_CITIES = {
    "tokyo", "london", "paris", "new york", "shanghai", "beijing", 
    "singapore", "bangkok", "mumbai", "seoul", "hong kong", "barcelona", 
    "rome", "amsterdam", "berlin", "dubai", "los angeles", "toronto"
}

# City relation IDs for major cities (OSM relation IDs)
CITY_RELATIONS = {
    # Europe
    "london": 175342,      # Greater London
    "paris": 71525,        # Paris
    "rome": 41485,         # Rome
    "barcelona": 347950,   # Barcelona
    "berlin": 62422,       # Berlin
    "amsterdam": 376317,  # Amsterdam
    "madrid": 2086243,     # Madrid
    "prague": 435460,      # Prague
    "vienna": 16667,       # Vienna
    "budapest": 219237,    # Budapest
    "stockholm": 1636723,  # Stockholm
    "copenhagen": 65936,   # Copenhagen
    "warsaw": 756496,      # Warsaw
    "athens": 158937,      # Athens
    "dublin": 2749059,     # Dublin
    "lisbon": 2080983,     # Lisbon
    
    # Asia
    "tokyo": 1543072,      # Tokyo
    "shanghai": 944826,    # Shanghai
    "beijing": 912940,     # Beijing
    "singapore": 536730,   # Singapore
    "bangkok": 1453939,    # Bangkok
    "mumbai": 1443122,     # Mumbai
    "seoul": 8560673,      # Seoul
    "hong kong": 912939,   # Hong Kong
    "kuala lumpur": 1734635, # Kuala Lumpur
    "jakarta": 1032485,    # Jakarta
    "manila": 936668,      # Manila
    "delhi": 108374,       # Delhi
    "osaka": 15026840,     # Osaka
    
    # Americas
    "new york": 175221,    # New York City  
    "los angeles": 165613, # Los Angeles
    "toronto": 148862,     # Toronto
    "mexico city": 135313, # Mexico City
    "são paulo": 595018,   # São Paulo
    "buenos aires": 166556, # Buenos Aires
    "vancouver": 238742,  # Vancouver
    "montreal": 204876,    # Montreal
    "chicago": 122884,     # Chicago
    "miami": 164566,       # Miami
    "rio de janeiro": 330288, # Rio de Janeiro
    
    # Middle East & Africa
    "dubai": 171068,       # Dubai
    "cairo": 2365365,     # Cairo
    "cape town": 1708595,  # Cape Town
    "johannesburg": 127329, # Johannesburg
    "tel aviv": 340216,    # Tel Aviv
    "istanbul": 2228692,   # Istanbul
    "marrakech": 335877,   # Marrakech
    "nairobi": 924940,     # Nairobi
    
    # Oceania
    "sydney": 488983,      # Sydney
    "melbourne": 1737754,  # Melbourne
    "auckland": 1737755,   # Auckland
}

# Fallback seed data
CITY_SEEDS = {
    # Europe
    "london": ["Westminster", "Camden", "Kensington", "Shoreditch", "Notting Hill"],
    "paris": ["Le Marais", "Montmartre", "Saint-Germain-des-Prés", "Latin Quarter", "Champs-Élysées"],
    "rome": ["Trastevere", "Monti", "Campo de' Fiori", "Vatican", "Trevi"],
    "barcelona": ["Gothic Quarter", "El Born", "Gràcia", "Eixample", "Barceloneta"],
    "berlin": ["Mitte", "Kreuzberg", "Prenzlauer Berg", "Friedrichshain", "Charlottenburg"],
    "amsterdam": ["Jordaan", "De Pijp", "Canal Ring", "Museum Quarter", "Red Light District"],
    "madrid": ["Sol", "Malasaña", "Chueca", "La Latina", "Salamanca"],
    "prague": ["Old Town", "Malá Strana", "Nové Město", "Vinohrady", "Žižkov"],
    "vienna": ["Innere Stadt", "Neubau", "Leopoldstadt", "Wieden", "Josefstadt"],
    "budapest": ["Buda", "Pest", "Óbuda", "Jewish Quarter", "Gellért Hill"],
    "stockholm": ["Gamla Stan", "Södermalm", "Östermalm", "Vasastan", "Kungsholmen"],
    "copenhagen": ["Indre By", "Vesterbro", "Nørrebro", "Østerbro", "Christianshavn"],
    "warsaw": ["Śródmieście", "Praga", "Wola", "Mokotów", "Żoliborz"],
    "athens": ["Plaka", "Monastiraki", "Kolonaki", "Psiri", "Exarchia"],
    "dublin": ["Temple Bar", "Grafton Street", "Docklands", "Rathmines", "Phibsborough"],
    "lisbon": ["Alfama", "Baixa", "Chiado", "Bairro Alto", "Belém"],
    
    # Asia
    "tokyo": ["Shibuya", "Shinjuku", "Harajuku", "Ginza", "Akihabara", "Ueno", "Tamachi", "Roppongi", "Ikebukuro", "Asakusa"],
    "shanghai": ["The Bund", "French Concession", "Jing'an", "Pudong", "Xintiandi"],
    "beijing": ["Forbidden City", "Hutongs", "Sanlitun", "Wangfujing", "798 Art District"],
    "singapore": ["Marina Bay", "Orchard Road", "Chinatown", "Little India", "Kampong Glam"],
    "bangkok": ["Sukhumvit", "Silom", "Khao San Road", "Chatuchak", "Old City"],
    "mumbai": ["Colaba", "Bandra", "Juhu", "Marine Drive", "Fort"],
    "seoul": ["Gangnam", "Myeongdong", "Hongdae", "Itaewon", "Insadong"],
    "hong kong": ["Central", "Tsim Sha Tsui", "Mong Kok", "Causeway Bay", "Stanley"],
    "kuala lumpur": ["KLCC", "Bukit Bintang", "Chinatown", "Bangsar", "Petaling Street"],
    "jakarta": ["Kota Tua", "Menteng", "Kemang", "Senayan", "Glodok"],
    "manila": ["Intramuros", "Makati", "Bonifacio", "Quezon City", "Pasay"],
    "delhi": ["Connaught Place", "Hauz Khas", "Chandni Chowk", "Khan Market", "Lutyens' Delhi"],
    "osaka": ["Dotonbori", "Shinsaibashi", "Umeda", "Namba", "Tennoji"],
    
    # Americas
    "new york": ["Manhattan", "Brooklyn", "Queens", "The Bronx", "Staten Island"],
    "los angeles": ["Hollywood", "Santa Monica", "Beverly Hills", "Venice Beach", "Downtown"],
    "toronto": ["Downtown", "Yorkville", "Queen West", "Kensington Market", "Distillery District"],
    "mexico city": ["Polanco", "Condesa", "Roma", "Coyoacán", "Centro Histórico"],
    "são paulo": ["Avenida Paulista", "Vila Madalena", "Jardins", "Liberdade", "Pinheiros"],
    "buenos aires": ["Palermo", "Recoleta", "San Telmo", "La Boca", "Puerto Madero"],
    "vancouver": ["Gastown", "Yaletown", "Kitsilano", "Granville Island", "Coal Harbour"],
    "montreal": ["Old Montreal", "Plateau", "Mile End", "Downtown", "Westmount"],
    "chicago": ["The Loop", "Lincoln Park", "Wicker Park", "Gold Coast", "River North"],
    "miami": ["South Beach", "Art Deco District", "Coconut Grove", "Wynwood", "Little Havana"],
    "rio de janeiro": ["Copacabana", "Ipanema", "Santa Teresa", "Lapa", "Leblon"],
    
    # Middle East & Africa
    "dubai": ["Downtown", "Dubai Marina", "Jumeirah", "Deira", "Business Bay"],
    "cairo": ["Downtown", "Zamalek", "Islamic Cairo", "Giza", "Heliopolis"],
    "cape town": ["V&A Waterfront", "Bo-Kaap", "Camps Bay", "City Bowl", "Constantia"],
    "johannesburg": ["Sandton", "Rosebank", "Melville", "Soweto", "Maboneng"],
    "tel aviv": ["White City", "Jaffa", "Neve Tzedek", "Rothschild Boulevard", "Florentin"],
    "istanbul": ["Sultanahmet", "Beyoğlu", "Karaköy", "Kadıköy", "Üsküdar"],
    "marrakech": ["Medina", "Gueliz", "Hivernage", "Marrakech Palmeraie", "Agdal"],
    "nairobi": ["Westlands", "Karen", "Nairobi CBD", "Lavington", "Kilimani"],
    "marseille": [],
    
    # Lyon suburbs
    "villeurbanne": ["Centre Villeurbanne", "Cusset", "Gratte-Ciel", "Charpennes", "Laurent Bonnevay"],
    "lyon": ["Vieux Lyon", "Croix-Rousse", "Presqu'île", "Confluence", "Part-Dieu", "Bellecour", "Fourvière", "Villeurbanne"],
    
    # Oceania
    "sydney": ["CBD", "The Rocks", "Darling Harbour", "Bondi", "Newtown"],
    "melbourne": ["CBD", "Fitzroy", "St Kilda", "South Yarra", "Brunswick"],
    "auckland": ["CBD", "Ponsonby", "Parnell", "Mission Bay", "Mount Eden"],
}


async def _fetch_london_boroughs() -> List[Dict]:
    """Direct fetch for London's 32 boroughs using Nominatim + Overpass"""
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Find Greater London via Nominatim
            params = {"q": "Greater London, UK", "format": "json", "limit": 3}
            headers = {"User-Agent": "CityGuides/1.0"}
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
                if r.status != 200:
                    return []
                results = await r.json()
                
                area_id = None
                for res in results:
                    if res.get("osm_type") == "relation" and res.get("osm_id"):
                        area_id = 3600000000 + int(res["osm_id"])
                        print(f"[DEBUG] Found London area_id: {area_id}")
                        break
                
                if not area_id:
                    return []
                
                # Step 2: Query Overpass for boroughs
                query = f"""
                [out:json][timeout:30];
                area({area_id})->.searchArea;
                (
                  relation["admin_level"="8"]["boundary"="administrative"](area.searchArea);
                );
                out tags;
                """
                
                async with session.post(OVERPASS_URL, data={"data": query}, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                    print(f"[DEBUG] Overpass status: {resp.status}")
                    if resp.status == 200:
                        j = await resp.json()
                        elements = j.get("elements", [])
                        print(f"[DEBUG] Overpass returned {len(elements)} elements")
                        boroughs = []
                        for el in elements:
                            name = el.get("tags", {}).get("name", "")
                            print(f"[DEBUG] Found: {name}")
                            if name:
                                boroughs.append({
                                    "name": name,
                                    "description": name,
                                    "type": "borough"
                                })
                        return sorted(boroughs, key=lambda x: x["name"])
                    else:
                        text = await resp.text()
                        print(f"[DEBUG] Overpass error: {text[:200]}")
        except Exception as e:
            print(f"[DEBUG] London boroughs fetch failed: {e}")
            import traceback
            traceback.print_exc()
    return []


async def _fetch_neighborhoods_nominatim(city: str) -> List[Dict]:
    """Fetch neighborhoods using Nominatim + Overpass with proper city identification"""
    async with aiohttp.ClientSession() as session:
        city_key = city.lower().strip()
        if "," in city_key:
            city_key = city_key.split(",")[0].strip()
        
        area_id = None
        
        # Step 1: Try to get area_id from CITY_RELATIONS first (more accurate)
        if city_key in CITY_RELATIONS:
            osm_relation_id = CITY_RELATIONS[city_key]
            area_id = 3600000000 + int(osm_relation_id)
            print(f"[DEBUG] Using CITY_RELATIONS for {city_key}: area_id {area_id}")
        else:
            # Step 1b: Find city via Nominatim (fallback)
            params = {"q": city, "format": "json", "limit": 5}
            headers = {"User-Agent": "CityGuides/1.0"}
            
            try:
                timeout = aiohttp.ClientTimeout(total=10)
                async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout) as r:
                    if r.status != 200:
                        return []
                    results = await r.json()
                    
                    for res in results:
                        if res.get("osm_type") == "relation" and res.get("osm_id"):
                            area_id = 3600000000 + int(res["osm_id"])
                            print(f"[DEBUG] Found {city_key} via Nominatim: area_id {area_id}")
                            break
            except Exception as e:
                print(f"[DEBUG] Nominatim search failed: {e}")
                return []
        
        if not area_id:
            return []
        
        # Step 2: Query Overpass for neighborhoods and boroughs
        try:
            query = f"""
            [out:json][timeout:25];
            area({area_id})->.searchArea;
            (
              relation["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.searchArea);
              way["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.searchArea);
              node["place"~"neighbourhood|suburb|quarter|city_district|district|locality"](area.searchArea);
              relation["admin_level"="8"]["boundary"="administrative"](area.searchArea);
              relation["admin_level"="9"]["boundary"="administrative"](area.searchArea);
            );
            out center tags;
            """
            
            async with session.post(OVERPASS_URL, data={"data": query}, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                if resp.status != 200:
                    return []
                j = await resp.json()
                elements = j.get("elements", [])
                
                neighborhoods = []
                seen = set()
                for el in elements:
                    tags = el.get("tags", {})
                    name = tags.get("name:en") or tags.get("name", "")
                    if name and name.lower() not in seen:
                        seen.add(name.lower())
                        neighborhoods.append({
                            "name": name,
                            "description": name,
                            "type": "culture"
                        })
                return neighborhoods
                
        except Exception as e:
            print(f"[DEBUG] Overpass query failed: {e}")
    return []


def get_neighborhood_suggestions(city: str, category: Optional[str] = None) -> List[Dict]:
    """
    Get neighborhood suggestions using Nominatim + Overpass.
    Falls back to seed data if provider returns empty.
    """
    city_key = city.lower().strip()
    if "," in city_key:
        city_key = city_key.split(",")[0].strip()
    
    # Special handling for London boroughs
    if city_key == "london":
        try:
            from city_guides.utils.async_utils import AsyncRunner
            boroughs = AsyncRunner.run(_fetch_london_boroughs())
            if len(boroughs) >= 32:
                print(f"[DEBUG] London: returning {len(boroughs)} boroughs")
                return boroughs[:32]
        except Exception as e:
            print(f"[DEBUG] London direct fetch failed: {e}")
    
    # Fall back to seed data (unless city is curated-only)
    city_key = city.lower().strip()
    if "," in city_key:
        city_key = city_key.split(",")[0].strip()
    
    # Skip Overpass for curated-only cities
    if city_key in CURATED_ONLY_CITIES:
        print(f"[DEBUG] {city_key}: curated-only city, skipping Overpass")
    else:
        # General case: Nominatim + Overpass
        try:
            from city_guides.utils.async_utils import AsyncRunner
            neighborhoods = AsyncRunner.run(_fetch_neighborhoods_nominatim(city_key))
            if len(neighborhoods) >= 4:
                print(f"[DEBUG] {city_key}: returning {len(neighborhoods)} neighborhoods")
                return neighborhoods[:32]
        except Exception as e:
            print(f"[DEBUG] Nominatim+Overpass failed: {e}")
    
    # Fall back to seed data
    seeds = CITY_SEEDS.get(city_key, [])
    print(f"[DEBUG] {city_key}: falling back to {len(seeds)} seed neighborhoods")
    
    # Check if seeds are strings or dictionaries
    if seeds and isinstance(seeds[0], str):
        return [
            {"name": name, "description": f"Neighborhood in {city_key.title()}", "type": "culture"}
            for name in seeds
        ]
    elif seeds and isinstance(seeds[0], dict):
        return seeds
    else:
        return []


def is_large_city(city: str) -> bool:
    """Check if city is large enough to warrant neighborhood suggestions"""
    city_key = city.lower().strip()
    if "," in city_key:
        city_key = city_key.split(",")[0].strip()
    return city_key in CITY_SEEDS or city_key in CITY_RELATIONS


def get_neighborhood_bbox(city: str, neighborhood: str) -> Optional[tuple]:
    """Get bounding box for a specific neighborhood"""
    return None
