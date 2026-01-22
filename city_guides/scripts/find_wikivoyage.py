#!/usr/bin/env python3
"""Find WikiVoyage projects in Wikimedia Enterprise API."""

import json
import requests
from pathlib import Path

token_file = Path(".wiki_token.json")
if not token_file.exists():
    print("❌ Token file not found. Run scripts/wiki_login.ps1 first.")
    exit(1)

with open(token_file) as f:
    token_data = json.load(f)

access_token = token_data.get("access_token")
if not access_token:
    print("❌ No access_token in .wiki_token.json")
    exit(1)

# Fetch all projects
url = "https://api.enterprise.wikimedia.com/v2/projects"
headers = {"Authorization": f"Bearer {access_token}"}
resp = requests.get(url, headers=headers, timeout=30)
resp.raise_for_status()
projects = resp.json()

# Find WikiVoyage projects
wikivoyage_projects = [p for p in projects if 'wikivoyage' in p.get('identifier', '').lower()]

print(f"Found {len(wikivoyage_projects)} WikiVoyage projects:")
print()
for p in wikivoyage_projects:
    identifier = p.get('identifier', 'N/A')
    language = p.get('language', 'N/A')
    name = p.get('name', 'N/A')
    print(f"  {identifier:20} ({language:5}) - {name}")

print()
print("Use the identifier (e.g., 'enwikivoyage') in your search_provider.py")
