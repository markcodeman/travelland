# Honest Hotel Finder - Alpha Prototype

A transparent hotel search engine with **no hidden fees** and honest pricing.

## Why This Exists
- LastMinute.com and others hide fees until checkout
- Users deserve upfront, honest pricing
- Simple, clean, trustworthy hotel search

## Features ✨
- ✅ **100% Transparent Pricing** - All taxes and fees shown upfront
- ✅ **No Fake Urgency** - Real availability only
- ✅ **Honest Policies** - Clear refund/cancellation terms
- ✅ **Free API** - 2,000 searches/month with Amadeus
- ✅ **Clean Interface** - No clutter, no tricks

## Setup (5 minutes)

### 1. Get FREE Amadeus API Keys
1. Go to https://developers.amadeus.com
2. Sign up (free)
3. Create a new app
4. Copy your API Key and API Secret

### 2. Install Dependencies
```powershell
cd hotel-finder
pip install -r requirements.txt
```

### 3. Configure API Keys
Create a `.env` file:
```
AMADEUS_API_KEY=your_api_key_here
AMADEUS_API_SECRET=your_api_secret_here
```

Or set them in `app.py` directly (line 12-13).

### 4. Run
```powershell
python app.py
```

Open http://localhost:5000 in your browser.

## Usage
1. Enter city code (NYC, LON, PAR, etc.)
2. Select dates and number of adults
3. Click "Search Hotels"
4. See **all prices upfront** - no surprises

## City Codes (IATA)
- NYC = New York
- LON = London
- PAR = Paris
- LAX = Los Angeles
- MIA = Miami
- LAS = Las Vegas
- DXB = Dubai
- SIN = Singapore

Full list: https://www.iata.org/en/publications/directories/code-search/

## API Limits (Free Tier)
- 2,000 requests/month
- Test environment (use production for real bookings)
- More than enough for alpha testing

## Honest Pricing Breakdown
Unlike LastMinute.com, we show:
```
Base Price:     $120.00  (nightly rate)
Taxes & Fees:   $ 18.50  (all taxes, service fees, etc.)
─────────────────────────
Total Price:    $138.50  (what you actually pay)
```

No "from $120" that becomes $180 at checkout.

## Future Features (Post-Alpha)
- [ ] Real booking capability
- [ ] User reviews (verified only)
- [ ] Price alerts
- [ ] Map view
- [ ] Compare saved hotels
- [ ] Mobile app

## Tech Stack
- Python 3.x + Flask
- Amadeus Hotel API
- Vanilla JavaScript (no bloat)
- Simple, fast, honest

## License
MIT - Build something better than LastMinute.com

## Contact
Built with honesty. No tricks, no gimmicks, no hidden fees.
