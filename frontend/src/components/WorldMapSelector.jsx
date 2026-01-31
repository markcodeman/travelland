import React, { useState, useRef, useEffect, useCallback } from 'react';
import './WorldMapSelector.css';

const WORLD_DESTINATIONS = {
  'Europe': {
    emoji: '🏰',
    countries: {
      'France': {
        emoji: '🇫🇷',
        cities: ['Paris', 'Lyon', 'Marseille', 'Nice', 'Bordeaux', 'Strasbourg'],
        coords: { x: 49, y: 28 },
        popular: true
      },
      'Spain': {
        emoji: '🇪🇸',
        cities: ['Barcelona', 'Madrid', 'Seville', 'Valencia', 'Granada', 'Bilbao'],
        coords: { x: 45, y: 35 },
        popular: true
      },
      'Italy': {
        emoji: '🇮🇹',
        cities: ['Rome', 'Venice', 'Florence', 'Milan', 'Naples', 'Verona'],
        coords: { x: 51, y: 37 },
        popular: true
      },
      'United Kingdom': {
        emoji: '🇬🇧',
        cities: ['London', 'Edinburgh', 'Manchester', 'Liverpool', 'Bath', 'Oxford'],
        coords: { x: 46, y: 22 },
        popular: true
      },
      'Germany': {
        emoji: '🇩🇪',
        cities: ['Berlin', 'Munich', 'Hamburg', 'Frankfurt', 'Cologne', 'Dresden'],
        coords: { x: 52, y: 26 },
        popular: true
      },
      'Netherlands': {
        emoji: '🇳🇱',
        cities: ['Amsterdam', 'Rotterdam', 'The Hague', 'Utrecht', 'Eindhoven', 'Maastricht'],
        coords: { x: 49, y: 30 },
        popular: false
      },
      'Portugal': {
        emoji: '🇵🇹',
        cities: ['Lisbon', 'Porto', 'Faro', 'Coimbra', 'Braga', 'Madeira'],
        coords: { x: 40, y: 42 },
        popular: false
      },
      'Sweden': {
        emoji: '🇸🇪',
        cities: ['Stockholm', 'Gothenburg', 'Malmö', 'Uppsala', 'Visby', 'Kiruna'],
        coords: { x: 52, y: 20 },
        popular: false
      },
      'Norway': {
        emoji: '🇳🇴',
        cities: ['Oslo', 'Bergen', 'Trondheim', 'Stavanger', 'Tromsø', 'Ålesund'],
        coords: { x: 50, y: 15 },
        popular: false
      },
      'Denmark': {
        emoji: '🇩🇰',
        cities: ['Copenhagen', 'Aarhus', 'Odense', 'Aalborg', 'Esbjerg', 'Roskilde'],
        coords: { x: 52, y: 30 },
        popular: false
      }
    }
  },
  'Asia': {
    emoji: '🏯',
    countries: {
      'Japan': {
        emoji: '🇯🇵',
        cities: ['Tokyo', 'Kyoto', 'Osaka', 'Hiroshima', 'Yokohama', 'Nara'],
        coords: { x: 82, y: 32 },
        popular: true
      },
      'China': {
        emoji: '🇨🇳',
        cities: ['Shanghai', 'Beijing', 'Hong Kong', 'Guangzhou', 'Shenzhen', 'Chengdu'],
        coords: { x: 75, y: 35 },
        popular: true
      },
      'India': {
        emoji: '🇮🇳',
        cities: ['Mumbai', 'Delhi', 'Bangalore', 'Kolkata', 'Chennai', 'Jaipur'],
        coords: { x: 68, y: 45 },
        popular: true
      }
    }
  },
  'Americas': {
    emoji: '🗽',
    countries: {
      'United States': {
        emoji: '🇺🇸',
        cities: ['New York', 'Los Angeles', 'Chicago', 'San Francisco', 'Miami', 'New Orleans'],
        coords: { x: 20, y: 38 },
        popular: true
      },
      'Canada': {
        emoji: '🇨🇦',
        cities: ['Toronto', 'Vancouver', 'Montreal', 'Calgary', 'Ottawa', 'Quebec City'],
        coords: { x: 22, y: 32 },
        popular: true
      },
      'Mexico': {
        emoji: '🇲🇽',
        cities: ['Mexico City', 'Guadalajara', 'Monterrey', 'Cancún', 'Playa del Carmen', 'Oaxaca'],
        coords: { x: 18, y: 45 },
        popular: true
      },
      'Brazil': {
        emoji: '🇧🇷',
        cities: ['Rio de Janeiro', 'São Paulo', 'Salvador', 'Brasília', 'Fortaleza', 'Recife'],
        coords: { x: 35, y: 65 },
        popular: true
      },
      'Argentina': {
        emoji: '🇦🇷',
        cities: ['Buenos Aires', 'Córdoba', 'Rosario', 'Mendoza', 'La Plata', 'Mar del Plata'],
        coords: { x: 32, y: 75 },
        popular: false
      }
    }
  },
  'Africa': {
    emoji: '🦁',
    countries: {
      'South Africa': {
        emoji: '🇿🇦',
        cities: ['Cape Town', 'Johannesburg', 'Durban', 'Pretoria', 'Port Elizabeth', 'Bloemfontein'],
        coords: { x: 55, y: 75 },
        popular: true
      }
    }
  },
  'Oceania': {
    emoji: '🏄',
    countries: {
      'Australia': {
        emoji: '🇦🇺',
        cities: ['Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Adelaide', 'Gold Coast'],
        coords: { x: 85, y: 75 },
        popular: true
      }
    }
  }
};

const POPULAR_DESTINATIONS = [
  { city: 'Paris', country: 'France', emoji: '🇫🇷', region: 'Europe' },
  { city: 'Tokyo', country: 'Japan', emoji: '🇯🇵', region: 'Asia' },
  { city: 'Barcelona', country: 'Spain', emoji: '🇪🇸', region: 'Europe' },
  { city: 'New York', country: 'United States', emoji: '🇺🇸', region: 'Americas' },
  { city: 'London', country: 'United Kingdom', emoji: '🇬🇧', region: 'Europe' },
  { city: 'Rome', country: 'Italy', emoji: '🇮🇹', region: 'Europe' },
  { city: 'Sydney', country: 'Australia', emoji: '🇦🇺', region: 'Oceania' },
  { city: 'Shanghai', country: 'China', emoji: '🇨🇳', region: 'Asia' }
];

const WorldMapSelector = ({ onLocationChange, onCityGuide }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedCountry, setSelectedCountry] = useState('');
  const [selectedCity, setSelectedCity] = useState('');
  const [showCityPanel, setShowCityPanel] = useState(false);
  const [hoveredRegion, setHoveredRegion] = useState('');
  const [sparkles, setSparkles] = useState([]);
  const searchRef = useRef(null);

  // Get all cities for search
  const getAllCities = useCallback(() => {
    const cities = [];
    Object.entries(WORLD_DESTINATIONS).forEach(([region, data]) => {
      Object.entries(data.countries).forEach(([country, countryData]) => {
        countryData.cities.forEach(city => {
          cities.push({
            city,
            country,
            emoji: countryData.emoji,
            region,
            popular: countryData.popular
          });
        });
      });
    });
    return cities;
  }, []);

  // Filter search suggestions
  const filteredSuggestions = getAllCities().filter(item => {
    const query = searchQuery.toLowerCase();
    return (
      item.city.toLowerCase().includes(query) ||
      item.country.toLowerCase().includes(query) ||
      item.region.toLowerCase().includes(query)
    );
  }).slice(0, 8);

  // Handle search selection
  const handleSearchSelect = useCallback((item) => {
    setSearchQuery(`${item.city}, ${item.country}`);
    setShowSuggestions(false);
    handleCitySelect(item.city, item.country, item.emoji);
  }, []);

  // Handle country click on map
  const handleCountryClick = useCallback((region, country, countryData) => {
    setSelectedCountry(country);
    setSelectedCity('');
    setShowCityPanel(true);
    
    // Generate sparkles
    const newSparkles = Array.from({ length: 6 }, (_, i) => ({
      id: Date.now() + i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      delay: Math.random() * 0.3
    }));
    setSparkles(newSparkles);
    setTimeout(() => setSparkles([]), 1500);
  }, []);

  // Handle city selection
  const handleCitySelect = useCallback((city, country = selectedCountry, emoji = '🏙️') => {
    setSelectedCity(city);
    setShowCityPanel(false);
    setSearchQuery(`${city}, ${country}`);
    
    // Trigger location change
    onLocationChange({
      country: country,
      countryName: country,
      city: city,
      cityName: city,
      state: '',
      stateName: '',
      neighborhood: '',
      neighborhoodName: '',
      intent: ''
    });

    // Trigger city guide
    setTimeout(() => {
      onCityGuide(city);
    }, 300);
  }, [selectedCountry, onLocationChange, onCityGuide]);

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="world-map-selector">
      {/* Search Bar */}
      <div className="search-container" ref={searchRef}>
        <div className="search-input-wrapper">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setShowSuggestions(e.target.value.length > 0);
            }}
            onFocus={() => setShowSuggestions(searchQuery.length > 0)}
            placeholder="🔍 Search cities, countries, or regions..."
            className="search-input"
          />
          {searchQuery && (
            <button
              className="clear-btn"
              onClick={() => {
                setSearchQuery('');
                setShowSuggestions(false);
              }}
            >
              ✕
            </button>
          )}
        </div>

        {/* Search Suggestions Dropdown */}
        {showSuggestions && filteredSuggestions.length > 0 && (
          <div className="search-suggestions">
            {filteredSuggestions.map((item, index) => (
              <div
                key={`${item.city}-${item.country}`}
                className={`suggestion-item ${item.popular ? 'popular' : ''}`}
                onClick={() => handleSearchSelect(item)}
              >
                <div className="suggestion-main">
                  <span className="suggestion-emoji">{item.emoji}</span>
                  <div className="suggestion-text">
                    <span className="suggestion-city">{item.city}</span>
                    <span className="suggestion-country">{item.country}</span>
                  </div>
                </div>
                {item.popular && <span className="popular-badge">⭐ Popular</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Popular Destinations */}
      <div className="popular-destinations">
        <h3>⭐ Popular Destinations</h3>
        <div className="popular-grid">
          {POPULAR_DESTINATIONS.map((dest) => (
            <button
              key={dest.city}
              className="popular-card"
              onClick={() => handleSearchSelect(dest)}
            >
              <span className="popular-emoji">{dest.emoji}</span>
              <span className="popular-city">{dest.city}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Interactive World Map */}
      <div className="world-map-container">
        <div className="world-map">
          {/* Europe */}
          <div
            className={`region europe ${hoveredRegion === 'Europe' ? 'hovered' : ''}`}
            onMouseEnter={() => setHoveredRegion('Europe')}
            onMouseLeave={() => setHoveredRegion('')}
          >
            <span className="region-emoji">🏰</span>
            <span className="region-name">Europe</span>
            {Object.entries(WORLD_DESTINATIONS.Europe.countries).map(([country, data]) => (
              <div
                key={country}
                className="country-marker"
                style={{ left: `${data.coords.x}%`, top: `${data.coords.y}%` }}
                onClick={() => handleCountryClick('Europe', country, data)}
                title={country}
              >
                {data.popular && <span className="marker-star">⭐</span>}
                <span className="marker-dot"></span>
              </div>
            ))}
          </div>

          {/* Asia */}
          <div
            className={`region asia ${hoveredRegion === 'Asia' ? 'hovered' : ''}`}
            onMouseEnter={() => setHoveredRegion('Asia')}
            onMouseLeave={() => setHoveredRegion('')}
          >
            <span className="region-emoji">🏯</span>
            <span className="region-name">Asia</span>
            {Object.entries(WORLD_DESTINATIONS.Asia.countries).map(([country, data]) => (
              <div
                key={country}
                className="country-marker"
                style={{ left: `${data.coords.x}%`, top: `${data.coords.y}%` }}
                onClick={() => handleCountryClick('Asia', country, data)}
                title={country}
              >
                {data.popular && <span className="marker-star">⭐</span>}
                <span className="marker-dot"></span>
              </div>
            ))}
          </div>

          {/* Americas */}
          <div
            className={`region americas ${hoveredRegion === 'Americas' ? 'hovered' : ''}`}
            onMouseEnter={() => setHoveredRegion('Americas')}
            onMouseLeave={() => setHoveredRegion('')}
          >
            <span className="region-emoji">🗽</span>
            <span className="region-name">Americas</span>
            {Object.entries(WORLD_DESTINATIONS.Americas.countries).map(([country, data]) => (
              <div
                key={country}
                className="country-marker"
                style={{ left: `${data.coords.x}%`, top: `${data.coords.y}%` }}
                onClick={() => handleCountryClick('Americas', country, data)}
                title={country}
              >
                {data.popular && <span className="marker-star">⭐</span>}
                <span className="marker-dot"></span>
              </div>
            ))}
          </div>

          {/* Africa */}
          <div
            className={`region africa ${hoveredRegion === 'Africa' ? 'hovered' : ''}`}
            onMouseEnter={() => setHoveredRegion('Africa')}
            onMouseLeave={() => setHoveredRegion('')}
          >
            <span className="region-emoji">🦁</span>
            <span className="region-name">Africa</span>
            {Object.entries(WORLD_DESTINATIONS.Africa.countries).map(([country, data]) => (
              <div
                key={country}
                className="country-marker"
                style={{ left: `${data.coords.x}%`, top: `${data.coords.y}%` }}
                onClick={() => handleCountryClick('Africa', country, data)}
                title={country}
              >
                {data.popular && <span className="marker-star">⭐</span>}
                <span className="marker-dot"></span>
              </div>
            ))}
          </div>

          {/* Oceania */}
          <div
            className={`region oceania ${hoveredRegion === 'Oceania' ? 'hovered' : ''}`}
            onMouseEnter={() => setHoveredRegion('Oceania')}
            onMouseLeave={() => setHoveredRegion('')}
          >
            <span className="region-emoji">🏄</span>
            <span className="region-name">Oceania</span>
            {Object.entries(WORLD_DESTINATIONS.Oceania.countries).map(([country, data]) => (
              <div
                key={country}
                className="country-marker"
                style={{ left: `${data.coords.x}%`, top: `${data.coords.y}%` }}
                onClick={() => handleCountryClick('Oceania', country, data)}
                title={country}
              >
                {data.popular && <span className="marker-star">⭐</span>}
                <span className="marker-dot"></span>
              </div>
            ))}
          </div>
        </div>

        {/* Sparkles */}
        {sparkles.map(sparkle => (
          <div
            key={sparkle.id}
            className="sparkle"
            style={{
              left: `${sparkle.x}%`,
              top: `${sparkle.y}%`,
              animationDelay: `${sparkle.delay}s`
            }}
          />
        ))}
      </div>

      {/* City Selection Panel */}
      {showCityPanel && selectedCountry && (
        <div className="city-panel">
          <div className="city-panel-header">
            <h3>
              {WORLD_DESTINATIONS[Object.keys(WORLD_DESTINATIONS).find(region => 
                WORLD_DESTINATIONS[region].countries[selectedCountry]
              )]?.countries[selectedCountry]?.emoji || '🏙️'} {selectedCountry}
            </h3>
            <button 
              className="close-btn"
              onClick={() => setShowCityPanel(false)}
            >
              ✕
            </button>
          </div>
          <div className="city-grid">
            {WORLD_DESTINATIONS[Object.keys(WORLD_DESTINATIONS).find(region => 
              WORLD_DESTINATIONS[region].countries[selectedCountry]
            )]?.countries[selectedCountry]?.cities.map(city => (
              <button
                key={city}
                className="city-card"
                onClick={() => handleCitySelect(city)}
              >
                <span className="city-name">{city}</span>
                <span className="city-sparkle">✨</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Selection Display */}
      {(selectedCountry || selectedCity) && (
        <div className="selection-display">
          {selectedCountry && (
            <div className="selection-item">
              <span>{WORLD_DESTINATIONS[Object.keys(WORLD_DESTINATIONS).find(region => 
                WORLD_DESTINATIONS[region].countries[selectedCountry]
              )]?.countries[selectedCountry]?.emoji || '🏙️'}</span>
              <span>{selectedCountry}</span>
            </div>
          )}
          {selectedCity && (
            <div className="selection-item">
              <span>🏙️</span>
              <span>{selectedCity}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default WorldMapSelector;
