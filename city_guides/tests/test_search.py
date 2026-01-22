import requests

url = "https://searx.org/search"
params = {"q": "best burger chesapeake", "format": "json", "categories": "general"}
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
resp = requests.get(url, params=params, headers=headers, timeout=15)
print(resp.status_code)
print(resp.text[:500])
