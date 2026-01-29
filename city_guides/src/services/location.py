# Location service - handles city mappings and fuzzy matching

# Common city mappings for quick recognition
city_mappings = {
    'paris': {'city': 'Paris', 'country': 'FR', 'countryName': 'France'},
    'tokyo': {'city': 'Tokyo', 'country': 'JP', 'countryName': 'Japan'},
    'london': {'city': 'London', 'country': 'GB', 'countryName': 'United Kingdom'},
    'new york': {'city': 'New York', 'country': 'US', 'countryName': 'United States', 'state': 'NY', 'stateName': 'New York'},
    'barcelona': {'city': 'Barcelona', 'country': 'ES', 'countryName': 'Spain', 'state': 'CT', 'stateName': 'Catalonia'},
    'rome': {'city': 'Rome', 'country': 'IT', 'countryName': 'Italy'},
    'amsterdam': {'city': 'Amsterdam', 'country': 'NL', 'countryName': 'Netherlands'},
    'berlin': {'city': 'Berlin', 'country': 'DE', 'countryName': 'Germany'},
    'lisbon': {'city': 'Lisbon', 'country': 'PT', 'countryName': 'Portugal'},
    'rio de janeiro': {'city': 'Rio de Janeiro', 'country': 'BR', 'countryName': 'Brazil', 'state': 'RJ', 'stateName': 'Rio de Janeiro'},
    'sydney': {'city': 'Sydney', 'country': 'AU', 'countryName': 'Australia', 'state': 'NSW', 'stateName': 'New South Wales'},
    'dubai': {'city': 'Dubai', 'country': 'AE', 'countryName': 'United Arab Emirates'},
    'singapore': {'city': 'Singapore', 'country': 'SG', 'countryName': 'Singapore'},
    'bangkok': {'city': 'Bangkok', 'country': 'TH', 'countryName': 'Thailand'},
    'mumbai': {'city': 'Mumbai', 'country': 'IN', 'countryName': 'India', 'state': 'MH', 'stateName': 'Maharashtra'},
    'toronto': {'city': 'Toronto', 'country': 'CA', 'countryName': 'Canada', 'state': 'ON', 'stateName': 'Ontario'},
    'vancouver': {'city': 'Vancouver', 'country': 'CA', 'countryName': 'Canada', 'state': 'BC', 'stateName': 'British Columbia'},
    'mexico city': {'city': 'Mexico City', 'country': 'MX', 'countryName': 'Mexico', 'state': 'DF', 'stateName': 'Distrito Federal'},
    'buenos aires': {'city': 'Buenos Aires', 'country': 'AR', 'countryName': 'Argentina'},
    'cape town': {'city': 'Cape Town', 'country': 'ZA', 'countryName': 'South Africa'},
    'cairo': {'city': 'Cairo', 'country': 'EG', 'countryName': 'Egypt'},
    'istanbul': {'city': 'Istanbul', 'country': 'TR', 'countryName': 'Turkey'},
    'moscow': {'city': 'Moscow', 'country': 'RU', 'countryName': 'Russia'},
    'madrid': {'city': 'Madrid', 'country': 'ES', 'countryName': 'Spain'},
    'prague': {'city': 'Prague', 'country': 'CZ', 'countryName': 'Czech Republic'},
    'vienna': {'city': 'Vienna', 'country': 'AT', 'countryName': 'Austria'},
    'budapest': {'city': 'Budapest', 'country': 'HU', 'countryName': 'Hungary'},
    'stockholm': {'city': 'Stockholm', 'country': 'SE', 'countryName': 'Sweden'},
    'oslo': {'city': 'Oslo', 'country': 'NO', 'countryName': 'Norway'},
    'helsinki': {'city': 'Helsinki', 'country': 'FI', 'countryName': 'Finland'},
    'copenhagen': {'city': 'Copenhagen', 'country': 'DK', 'countryName': 'Denmark'},
    'warsaw': {'city': 'Warsaw', 'country': 'PL', 'countryName': 'Poland'},
    'athens': {'city': 'Athens', 'country': 'GR', 'countryName': 'Greece'},
    'dublin': {'city': 'Dublin', 'country': 'IE', 'countryName': 'Ireland'},
    'reykjavik': {'city': 'Reykjavik', 'country': 'IS', 'countryName': 'Iceland'},
    'zurich': {'city': 'Zurich', 'country': 'CH', 'countryName': 'Switzerland'},
    'tysons': {'city': 'Tysons', 'country': 'US', 'countryName': 'United States', 'state': 'VA', 'stateName': 'Virginia'},
    'virginia': {'city': 'Richmond', 'country': 'US', 'countryName': 'United States', 'state': 'VA', 'stateName': 'Virginia'}
}

# Region mappings for areas that aren't specific cities
region_mappings = {
    'swiss alps': {'city': 'Zurich', 'country': 'CH', 'countryName': 'Switzerland', 'region': 'Swiss Alps'},
    'alps': {'city': 'Zurich', 'country': 'CH', 'countryName': 'Switzerland', 'region': 'Alps'},
    'caribbean': {'city': 'Nassau', 'country': 'BS', 'countryName': 'Bahamas', 'region': 'Caribbean'},
    'mediterranean': {'city': 'Barcelona', 'country': 'ES', 'countryName': 'Spain', 'region': 'Mediterranean'},
    'balkans': {'city': 'Athens', 'country': 'GR', 'countryName': 'Greece', 'region': 'Balkans'},
    'scandinavia': {'city': 'Stockholm', 'country': 'SE', 'countryName': 'Sweden', 'region': 'Scandinavia'},
    'rocky mountains': {'city': 'Denver', 'country': 'US', 'countryName': 'United States', 'region': 'Rocky Mountains'},
    'himalayas': {'city': 'Kathmandu', 'country': 'NP', 'countryName': 'Nepal', 'region': 'Himalayas'},
    'sahara': {'city': 'Cairo', 'country': 'EG', 'countryName': 'Egypt', 'region': 'Sahara'},
    'virginia': {'city': 'Richmond', 'country': 'US', 'countryName': 'United States', 'region': 'Virginia'}
}

def levenshtein_distance(s1, s2):
    """Calculate Levenshtein distance between two strings"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def find_best_match(query, options, max_distance=3):
    """Find best fuzzy match from options"""
    best_match = None
    best_score = float('inf')
    
    for option in options:
        distance = levenshtein_distance(query, option)
        if distance <= max_distance and distance < best_score:
            best_score = distance
            best_match = option
    
    return best_match
