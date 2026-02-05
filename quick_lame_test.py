#!/usr/bin/env python3
import re

print('🔍 QUICK LAMENESS ANALYSIS')
print('=' * 40)

# Check fun facts
try:
    with open('city_guides/src/app.py', 'r') as f:
        content = f.read()
    fun_fact_cities = re.findall(r"'([^']+)': \[", content)
    print(f'📝 Cities with fun facts: {len(fun_fact_cities)}')
except:
    fun_fact_cities = []
    print('📝 Cities with fun facts: 0')

# Check location services
try:
    with open('city_guides/src/services/location.py', 'r') as f:
        content = f.read()
    location_cities = re.findall(r"'([^']+)': {'city'", content)
    print(f'📍 Cities with location data: {len(location_cities)}')
except:
    location_cities = []
    print('📍 Cities with location data: 0')

# Check category mappings
try:
    with open('city_guides/src/simple_categories.py', 'r') as f:
        content = f.read()
    category_cities = re.findall(r"# ([^ ]+) specific", content)
    print(f'🎨 Cities with category mappings: {len(category_cities)}')
except:
    category_cities = []
    print('🎨 Cities with category mappings: 0')

print()
print('🚨 LAME CITIES (Missing Fun Facts):')

# Find cities that have location but no fun facts
lame_cities = []
for city in location_cities:
    if city not in fun_fact_cities:
        lame_cities.append(city)

print(f'  Total lame cities: {len(lame_cities)}')
print(f'  Sample: {lame_cities[:10]}')

print()
print('🎯 BEST SUPPORTED CITIES:')
best_cities = []
for city in fun_fact_cities:
    if city in location_cities and city in category_cities:
        best_cities.append(city)

print(f'  Total best cities: {len(best_cities)}')
print(f'  Sample: {best_cities[:10]}')
