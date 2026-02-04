#!/usr/bin/env python3
"""
Test fun fact quality on 500 random cities (excluding 100 well-known)
"""
import asyncio
import aiohttp
import json
import random
from pathlib import Path
import sys
sys.path.insert(0, '.')

# Well-known cities to exclude
WELL_KNOWN_CITIES = {
    # Europe
    'paris', 'london', 'rome', 'barcelona', 'amsterdam', 'berlin', 'madrid', 'vienna', 'prague', 'budapest',
    'athens', 'lisbon', 'stockholm', 'copenhagen', 'oslo', 'helsinki', 'warsaw', 'krakow', 'dublin', 'brussels',
    'milan', 'venice', 'florence', 'munich', 'zurich', 'geneva', 'moscow', 'st petersburg', 'istanbul', 'kiev',
    
    # Americas
    'new york', 'los angeles', 'chicago', 'miami', 'san francisco', 'boston', 'washington', 'seattle', 'atlanta', 'dallas',
    'toronto', 'vancouver', 'montreal', 'mexico city', 'buenos aires', 'rio de janeiro', 'são paulo', 'lima', 'bogota', 'santiago',
    
    # Asia
    'tokyo', 'osaka', 'kyoto', 'seoul', 'beijing', 'shanghai', 'hong kong', 'singapore', 'bangkok', 'kuala lumpur',
    'jakarta', 'manila', 'ho chi minh city', 'delhi', 'mumbai', 'dubai', 'tel aviv', 'jerusalem',
    
    # Africa
    'cairo', 'cape town', 'casablanca', 'lagos', 'nairobi',
    
    # Oceania
    'sydney', 'melbourne', 'brisbane', 'perth', 'auckland', 'wellington'
}

# Random city list (500 cities from various countries)
TEST_CITIES = [
    # Europe (smaller cities)
    'bruges', 'ghent', 'antwerp', 'brussels', 'liege', 'namur', 'charleroi', 'mons', 'mechelen', 'leuven',
    'rotterdam', 'the hague', 'utrecht', 'eindhoven', 'groningen', 'maastricht', 'tilburg', 'breda', 'apeldoorn', 'nijmegen',
    'lyon', 'marseille', 'nice', 'toulouse', 'nantes', 'strasbourg', 'bordeaux', 'lille', 'rennes', 'reims',
    'bergamo', 'brescia', 'verona', 'padua', 'treviso', 'vicenza', 'modena', 'parma', 'reggio emilia', 'ravenna',
    'salzburg', 'innsbruck', 'graz', 'linz', 'klagenfurt', 'bregenz', 'villach', 'wels', 'st. pölten', 'dornbirn',
    'krakow', 'wroclaw', 'gdansk', 'poznan', 'lodz', 'szczecin', 'lublin', 'katowice', 'bydgoszcz', 'gdynia',
    'brno', 'ostrava', 'plzen', 'liberec', 'olomouc', 'budweis', 'hradec kralove', 'usti nad labem', 'pardubice', 'havirov',
    'debrecen', 'szeged', 'pecs', 'gyor', 'nyiregyhaza', 'kecskemet', 'szekesfehervar', 'szombathely', 'szolnok', 'tatabanya',
    'cluj-napoca', 'timisoara', 'iasi', 'constanta', 'craiova', 'brasov', 'galati', 'ploiesti', 'oradea', 'braila',
    'varna', 'burgas', 'plovdiv', 'ruse', 'stara zagora', 'pleven', 'sliven', 'dimitrovgrad', 'pazardzhik', 'asenovgrad',
    'split', 'rijeka', 'osijek', 'zadar', 'pula', 'slavonski brod', 'karlovac', 'velika gorica', 'varazdin', 'dubrovnik',
    'coimbra', 'porto', 'braga', 'faro', 'funchal', 'aveiro', 'leiria', 'vila nova de gaia', 'setubal', 'almada',
    'valencia', 'seville', 'zaragoza', 'malaga', 'murcia', 'palma', 'las palmas', 'bilbao', 'alicante', 'valladolid',
    'genoa', 'turin', 'naples', 'bologna', 'florence', 'catania', 'verona', 'messina', 'padua', 'trieste',
    'sheffield', 'manchester', 'birmingham', 'leeds', 'glasgow', 'edinburgh', 'cardiff', 'belfast', 'bristol', 'liverpool',
    'dusseldorf', 'cologne', 'frankfurt', 'stuttgart', 'dortmund', 'essen', 'leipzig', 'bremen', 'hannover', 'nuernberg',
    'gothenburg', 'malmo', 'uppsala', 'vasteras', 'orebro', 'linkoping', 'helsingborg', 'jonkoping', 'norrkoping', 'umea',
    'tampere', 'espoo', 'vantaa', 'turku', 'oulu', 'jyvaskyla', 'lahti', 'kuopio', 'pori', 'kouvola',
    'bergen', 'trondheim', 'stavanger', 'fredrikstad', 'tromso', 'sandnes', 'drammen', 'skien', 'sarpsborg', 'kristiansand',
    'aalborg', 'odense', 'esbjerg', 'randers', 'kolding', 'horsens', 'vejle', 'roskilde', 'silkeborg', 'naestved',
    'tallinn', 'tartu', 'narva', 'parnu', 'kohtla-jarve', 'viljandi', 'rakvere', 'maardu', 'sillamae', 'kuressaare',
    'riga', 'daugavpils', 'liepaja', 'jelgava', 'jurmala', 'ventspils', 'rezekne', 'valmiera', 'ogre', 'tukums',
    'vilnius', 'kaunas', 'klaipeda', 'siauliai', 'panevezys', 'alytus', 'marijampole', 'mazeikiai', 'jonava', 'uten',
    'nicaragua', 'costa rica', 'panama', 'guatemala', 'belize', 'el salvador', 'honduras',
    
    # Americas (lesser-known)
    'quebec city', 'montreal', 'vancouver', 'calgary', 'edmonton', 'ottawa', 'winnipeg', 'halifax', 'victoria', 'saskatoon',
    'guadalajara', 'monterrey', 'puebla', 'tijuana', 'leon', 'juarez', 'zapopan', 'santiago de queretaro', 'morelia', 'veracruz',
    'cordoba', 'rosario', 'mendoza', 'la plata', 'mar del plata', 'salta', 'san miguel de tucuman', 'santa fe', 'bahia blanca', 'san juan',
    'valparaiso', 'concepcion', 'la serena', 'antofagasta', 'temuco', 'rancagua', 'talca', 'arica', 'chillan', 'iquique',
    'arequipa', 'trujillo', 'chiclayo', 'iquitos', 'huancayo', 'piura', 'cajamarca', 'huanuco', 'pucallpa', 'tarapoto',
    'guayaquil', 'cuenca', 'santo domingo', 'ambato', 'manta', 'portoviejo', 'machala', 'loja', 'ibarra', 'esmeraldas',
    'medellin', 'cali', 'barranquilla', 'cartagena', 'cucuta', 'soledad', 'ibague', 'bucaramanga', 'soacha', 'pereira',
    'maracaibo', 'valencia', 'barquisimeto', 'maracay', 'ciudad guayana', 'san cristobal', 'maturin', 'barcelona', 'merida', 'cumana',
    'la paz', 'santa cruz', 'cochabamba', 'sucre', 'oruro', 'potosi', 'sacaba', 'tarija', 'trinidad', 'riberalta',
    'montevideo', 'salto', 'paysandu', 'las piedras', 'rivera', 'melo', 'tacuarembo', 'artigas', 'minas', 'fray bentos',
    'asuncion', 'ciudad del este', 'san lorenzo', 'luque', 'caaguazu', 'coronel oviedo', 'encarnacion', 'pedro juan caballero', 'concepcion', 'villa hayes',
    'georgetown', 'paramaribo', 'cayenne',
    
    # Asia (lesser-known)
    'kobe', 'kyoto', 'nagoya', 'sapporo', 'fukuoka', 'kawasaki', 'saitama', 'hiroshima', 'sendai', 'chiba',
    'busan', 'daegu', 'incheon', 'gwangju', 'daejeon', 'ulsan', 'suwon', 'anyang', 'cheongju', 'jeonju',
    'shenyang', 'guangzhou', 'shenzhen', 'dongguan', 'tianjin', 'nanjing', 'wuhan', 'chengdu', 'hangzhou', 'xian',
    'penang', 'johor bahru', 'malacca', 'ipoh', 'kuching', 'kinabalu', 'klang', 'subang jaya', 'shah alam', 'putrajaya',
    'surabaya', 'bandung', 'medan', 'semarang', 'makassar', 'palembang', 'tangerang', 'depok', 'batam', 'pekalongan',
    'cebu', 'davao', 'cagayan de oro', 'iloilo', 'bacolod', 'general santos', 'dipolog', 'legazpi', 'butuan', 'zamboanga',
    'pattaya', 'chiang mai', 'phuket', 'hat yai', 'nakhon ratchasima', 'udon thani', 'khon kaen', 'nakhon si thammarat', 'songkhla', 'rayong',
    'yangon', 'mandalay', 'naypyidaw', 'mawlamyine', 'bago', 'pathein', 'monywa', 'meiktila', 'sittwe', 'taunggyi',
    'ho chi minh city', 'hanoi', 'da nang', 'hai phong', 'can tho', 'bien hoa', 'hue', 'nha trang', 'vung tau', 'buon ma thuot',
    'bandar seri begawan', 'phnom penh', 'siem reap', 'vientiane', 'luang prabang', 'savannakhet', 'pakse', 'thakhek', 'sam neua', 'phongsaly',
    'kathmandu', 'pokhara', 'lalitpur', 'bharatpur', 'biratnagar', 'birgunj', 'dharan', 'hetauda', 'janakpur', 'bhimdatta',
    'dhaka', 'chittagong', 'khulna', 'rajshahi', 'sylhet', 'barisal', 'rangpur', 'comilla', 'narayanganj', 'mymensingh',
    'karachi', 'lahore', 'faisalabad', 'rawalpindi', 'multan', 'gujranwala', 'peshawar', 'quetta', 'islamabad', 'sialkot',
    'ahmedabad', 'bangalore', 'hyderabad', 'pune', 'kolkata', 'surat', 'jaipur', 'lucknow', 'kanpur', 'nagpur',
    'tabriz', 'mashhad', 'isfahan', 'karaj', 'shiraz', 'qom', 'kermanshah', 'urmia', 'rasht', 'zahedan',
    'aleppo', 'homs', 'latakia', 'hama', 'deir ez-zor', 'idlib', 'daraa', 'al-hasakah', 'raqqa', 'jableh',
    'gaza', 'khan yunis', 'rafah', 'deir al-balah', 'nuseirat', 'jabalia', 'beit hanoun', 'beit lahiya', 'abasan',
    
    # Africa (lesser-known)
    'alexandria', 'giza', 'shubra el-kheima', 'port said', 'suez', 'luxor', 'asyut', 'mansoura', 'tanta', 'damanhur',
    'johannesburg', 'durban', 'pretoria', 'cape town', 'port elizabeth', 'bloemfontein', 'east london', 'pietermaritzburg', 'nelson mandela bay', 'polokwane',
    'casablanca', 'rabat', 'marrakech', 'fes', 'meknes', 'tangier', 'oujda', 'kenitra', 'agadir', 'tetouan',
    'lagos', 'kano', 'ibadan', 'kaduna', 'port harcourt', 'benin city', 'maiduguri', 'zaria', 'aba', 'jos',
    'nairobi', 'mombasa', 'kisumu', 'nakuru', 'eldoret', 'kehancha', 'kitale', 'thika', 'malindi', 'garissa',
    'addis ababa', 'dire dawa', 'mekelle', 'gondar', 'bahir dar', 'hawassa', 'jimma', 'jijiga', 'dessie', 'shashamane',
    'dar es salaam', 'mwanza', 'arusha', 'dodoma', 'mbeya', 'morogoro', 'tanga', 'kigoma', 'moshi', 'tabora',
    'kampala', 'gulu', 'lira', 'mbarara', 'jinja', 'entebbe', 'mbale', 'masaka', 'mukono', 'busia',
    'kumasi', 'tamale', 'takoradi', 'ashaiman', 'tema', 'obuasi', 'sekondi-takoradi', 'cape coast', 'koforidua', 'wa',
    'abidjan', 'bouake', 'daloa', 'yamoussoukro', 'korhogo', 'san pedro', 'duékoué', 'dabou', 'gagnoa', 'man',
    'accra', 'kumasi', 'tamale', 'takoradi', 'ashaiman', 'tema', 'obuasi', 'sekondi-takoradi', 'cape coast', 'koforidua',
    'antananarivo', 'toamasina', 'antsirabe', 'mahajanga', 'fianarantsoa', 'toliara', 'antsiranana', 'ambovombe', 'amparafaravola', 'maintirano',
    'harare', 'bulawayo', 'chitungwiza', 'mutare', 'gwanda', 'gweru', 'kadoma', 'kariba', 'marondera', 'victoria falls',
    'lilongwe', 'blantyre', 'mzuzu', 'zomba', 'karonga', 'kasungu', 'salima', 'liwonde', 'nkhata bay', 'balaka',
    'maputo', 'matola', 'nampula', 'beira', 'chimoio', 'quelimane', 'tete', 'xai-xai', 'lichinga', 'pemba',
    'luanda', 'huambo', 'lobito', 'kuito', 'lubango', 'malanje', 'namibe', 'soyo', 'cabinda', 'sumbe',
    
    # Oceania (lesser-known)
    'adelaide', 'newcastle', 'canberra', 'gold coast', 'wollongong', 'logan city', 'geelong', 'townsville', 'cairns', 'darwin',
    'new plymouth', 'napier-hastings', 'rotorua', 'hamilton', 'tauranga', 'lower hutt', 'upper hutt', 'whangarei', 'gisborne', 'timaru',
    'suva', 'nadi', 'labasa', 'ba', 'tavua', 'rakiraki', 'levuka', 'savusavu', 'sigatoka', 'lautoka',
    'port moresby', 'lae', 'madang', 'mount hagen', 'kokopo', 'rabaul', 'kimbe', 'goroka', 'wewak', 'popondetta',
    'honolulu', 'pearl city', 'hilo', 'kailua', 'waipahu', 'kaneohe', 'mililani town', 'kahului', 'kihei', 'kailua-kona'
]

def filter_well_known(cities):
    """Remove well-known cities from test list"""
    filtered = []
    for city in cities:
        city_lower = city.lower()
        # Skip if matches any well-known city
        if any(known in city_lower or city_lower in known for known in WELL_KNOWN_CITIES):
            continue
        filtered.append(city)
    return filtered

async def test_fun_fact_quality(session, city):
    """Test fun fact quality for a single city"""
    try:
        async with session.post(
            'http://localhost:5010/api/fun-fact',
            json={'city': city},
            headers={'Content-Type': 'application/json'}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                fact = data.get('funFact', '')
                return city, fact, True
            else:
                return city, f"HTTP {resp.status}", False
    except Exception as e:
        return city, str(e), False

async def run_quality_test(num_cities=500):
    """Run quality test on random cities"""
    # Filter out well-known cities
    available_cities = filter_well_known(TEST_CITIES)
    
    # Select random cities
    test_cities = random.sample(available_cities, min(num_cities, len(available_cities)))
    
    print(f"Testing {len(test_cities)} random cities (excluding {len(WELL_KNOWN_CITIES)} well-known)")
    print("=" * 60)
    
    results = []
    async with aiohttp.ClientSession() as session:
        # Test cities in batches
        batch_size = 20
        for i in range(0, len(test_cities), batch_size):
            batch = test_cities[i:i+batch_size]
            tasks = [test_fun_fact_quality(session, city) for city in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    print(f"❌ Batch error: {result}")
                else:
                    city, fact, success = result
                    results.append((city, fact, success))
                    
                    # Show progress
                    status = "✅" if success else "❌"
                    fact_preview = fact[:60] + "..." if len(fact) > 60 else fact
                    print(f"{status} {city}: {fact_preview}")
            
            # Small delay between batches
            await asyncio.sleep(0.5)
    
    # Calculate statistics
    total = len(results)
    successful = sum(1 for _, _, success in results if success)
    failed = total - successful
    
    # Quality analysis
    from city_guides.src.fun_fact_tracker import FunFactTracker
    tracker = FunFactTracker()
    
    generic_count = 0
    specific_count = 0
    
    for city, fact, success in results:
        if success:
            score = tracker.calculate_quality_score(fact)
            if score < 0.3:
                generic_count += 1
            else:
                specific_count += 1
    
    print("\n" + "=" * 60)
    print("📊 QUALITY TEST RESULTS")
    print("=" * 60)
    print(f"Total cities tested: {total}")
    print(f"Successful requests: {successful} ({successful/total*100:.1f}%)")
    print(f"Failed requests: {failed} ({failed/total*100:.1f}%)")
    print(f"Generic facts: {generic_count} ({generic_count/total*100:.1f}%)")
    print(f"Specific facts: {specific_count} ({specific_count/total*100:.1f}%)")
    
    # Show worst examples
    print("\n🔍 WORST QUALITY EXAMPLES:")
    worst = [(city, fact) for city, fact, success in results if success]
    worst.sort(key=lambda x: tracker.calculate_quality_score(x[1]))
    
    for city, fact in worst[:5]:
        score = tracker.calculate_quality_score(fact)
        print(f"  {city}: {fact[:80]}... (score: {score:.2f})")
    
    # Show best examples
    print("\n⭐ BEST QUALITY EXAMPLES:")
    best = [(city, fact) for city, fact, success in results if success]
    best.sort(key=lambda x: tracker.calculate_quality_score(x[1]), reverse=True)
    
    for city, fact in best[:5]:
        score = tracker.calculate_quality_score(fact)
        print(f"  {city}: {fact[:80]}... (score: {score:.2f})")
    
    # Generate report
    report = {
        'timestamp': str(asyncio.get_event_loop().time()),
        'total_cities': total,
        'successful': successful,
        'failed': failed,
        'generic_facts': generic_count,
        'specific_facts': specific_count,
        'results': results
    }
    
    report_file = Path('quality_test_report.json')
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Full report saved to: {report_file}")
    
    return report

if __name__ == "__main__":
    asyncio.run(run_quality_test(500))
