# Future Tools & Free API Integrations

This document lists ideas for future features and integrations using free or open APIs. Each tool includes a short description and suggested API(s).

---

## 1. Weather Widget
- **Description:** Show current weather and forecast for the selected city.
- **APIs:** Open-Meteo, OpenWeatherMap (free tier)
- **Notes:** Cache results to avoid hitting rate limits.

## 2. Public Transit Finder
- **Description:** Show nearest transit stops, schedules, or route planning.
- **APIs:** TransportAPI (UK), OpenTripPlanner, local GTFS feeds
- **Notes:** May require city-specific data sources.

## 3. Local Events/Activities
- **Description:** List upcoming events, concerts, or meetups in the city.
- **APIs:** Eventbrite, Ticketmaster Discovery, Meetup (limited)
- **Notes:** Filter by date/location; some APIs require attribution.

## 4. Currency Exchange Rate Trends
- **Description:** Show historical exchange rates or charts.
- **APIs:** exchangerate.host, Frankfurter.app
- **Notes:** Can be combined with the existing converter.

## 5. Air Quality Index
- **Description:** Display current air quality and health tips.
- **APIs:** OpenAQ, IQAir
- **Notes:** Show color-coded AQI and health recommendations.

## 6. Wikipedia City Summary
- **Description:** Show a short intro and image for the city.
- **APIs:** Wikipedia REST API
- **Notes:** Use for city overviews or fun facts.

## 7. Local News Headlines
- **Description:** Show top news for the city/region.
- **APIs:** NewsAPI (free tier), Mediastack, GNews
- **Notes:** Filter by region/language; respect API terms.

## 8. Sunrise/Sunset Times
- **Description:** Show today’s sunrise/sunset for the city.
- **APIs:** sunrise-sunset.org
- **Notes:** Simple, no auth required.

## 9. Nearby WiFi Hotspots
- **Description:** List public WiFi locations.
- **APIs:** OpenWiFiMap, OpenData city feeds
- **Notes:** Useful for travelers; may need city-specific data.

## 10. Language Phrasebook
- **Description:** Show basic phrases in the local language.
- **APIs:** Glosbe, Tatoeba, or static data
- **Notes:** Can be static or fetched; add audio for extra value.

---

## General Implementation Notes
- Always check API terms of use and attribution requirements.
- Cache or rate-limit requests to avoid hitting free tier limits.
- Prefer APIs with CORS support for direct browser calls, or proxy via Flask if needed.
- Add UI/UX hints for beta/experimental features.
- Document each integration in the main README when implemented.

---

*Last updated: January 7, 2026*