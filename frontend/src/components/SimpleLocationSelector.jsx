import { useCallback, useEffect, useMemo, useState } from 'react';
import './SimpleLocationSelector.css';

const POPULAR_DESTINATIONS = [
  { city: 'Paris', country: 'France', emoji: '🇫🇷' },
  { city: 'Tokyo', country: 'Japan', emoji: '🇯🇵' },
  { city: 'Barcelona', country: 'Spain', emoji: '🇪🇸' },
  { city: 'New York', country: 'United States', emoji: '🇺🇸' },
  { city: 'London', country: 'United Kingdom', emoji: '🇬🇧' },
  { city: 'Rome', country: 'Italy', emoji: '🇮🇹' },
  { city: 'Sydney', country: 'Australia', emoji: '🇦🇺' },
  { city: 'Shanghai', country: 'China', emoji: '🇨🇳' },
  { city: 'Amsterdam', country: 'Netherlands', emoji: '🇳🇱' },
  { city: 'Berlin', country: 'Germany', emoji: '🇩🇪' },
  { city: 'Lisbon', country: 'Portugal', emoji: '🇵🇹' },
  { city: 'Dubai', country: 'United Arab Emirates', emoji: '🇦🇪' },
  { city: 'Singapore', country: 'Singapore', emoji: '🇸🇬' },
  { city: 'Hong Kong', country: 'Hong Kong', emoji: '🇭🇰' },
  { city: 'Mumbai', country: 'India', emoji: '🇮🇳' },
  { city: 'Toronto', country: 'Canada', emoji: '🇨🇦' }
];

const HIDDEN_GEMS = [
  { city: 'Paris', neighborhood: 'Le Marais', country: 'France', emoji: '��', description: 'Historic Jewish quarter, LGBTQ+ friendly' },
  { city: 'London', neighborhood: 'Notting Hill', country: 'United Kingdom', emoji: '��', description: 'Colorful houses and Portobello market' },
  { city: 'New York City', neighborhood: 'Greenwich Village', country: 'United States', emoji: '��', description: 'Bohemian history and jazz clubs' },
  { city: 'Rome', neighborhood: 'Trastevere', country: 'Italy', emoji: '🇮🇹', description: 'Bohemian riverside with trattorias' },
  { city: 'Barcelona', neighborhood: 'El Born', country: 'Spain', emoji: '��', description: 'Trendy medieval quarter' },
  { city: 'Tokyo', neighborhood: 'Shibuya', country: 'Japan', emoji: '��', description: 'Youth culture, fashion, and nightlife' },
  { city: 'Paris', neighborhood: 'Montmartre', country: 'France', emoji: '🇫🇷', description: 'Artist hill with village atmosphere' },
  { city: 'London', neighborhood: 'Shoreditch', country: 'United Kingdom', emoji: '��', description: 'Street art and hipster nightlife' },
  { city: 'Tokyo', neighborhood: 'Harajuku', country: 'Japan', emoji: '��', description: 'Street fashion and quirky culture' },
  { city: 'Bangkok', neighborhood: 'Sukhumvit', country: 'Thailand', emoji: '🇹🇭', description: 'Expat nightlife, malls, and street food' },
  { city: 'Rome', neighborhood: 'Monti', country: 'Italy', emoji: '�🇹', description: 'Vintage shopping and aperitivo culture' },
  { city: 'Barcelona', neighborhood: 'Gràcia', country: 'Spain', emoji: '��', description: 'Village atmosphere with plazas' }
];

const ALL_DESTINATIONS = [
  // Europe
  { city: 'Paris', country: 'France', emoji: '🇫🇷' },
  { city: 'Lyon', country: 'France', emoji: '🇫🇷' },
  { city: 'Marseille', country: 'France', emoji: '🇫🇷' },
  { city: 'Nice', country: 'France', emoji: '🇫🇷' },
  { city: 'Bordeaux', country: 'France', emoji: '🇫🇷' },
  { city: 'Strasbourg', country: 'France', emoji: '🇫🇷' },
  
  // US cities (for ambiguous names)
  { city: 'Lyon', country: 'United States', state: 'Mississippi', emoji: '🇺🇸' },
  { city: 'Barcelona', country: 'Spain', emoji: '🇪🇸' },
  { city: 'Madrid', country: 'Spain', emoji: '🇪🇸' },
  { city: 'Seville', country: 'Spain', emoji: '🇪🇸' },
  { city: 'Valencia', country: 'Spain', emoji: '🇪🇸' },
  { city: 'Granada', country: 'Spain', emoji: '🇪🇸' },
  { city: 'Bilbao', country: 'Spain', emoji: '🇪🇸' },
  { city: 'Rome', country: 'Italy', emoji: '🇮🇹' },
  { city: 'Venice', country: 'Italy', emoji: '🇮🇹' },
  { city: 'Florence', country: 'Italy', emoji: '🇮🇹' },
  { city: 'Milan', country: 'Italy', emoji: '🇮🇹' },
  { city: 'Naples', country: 'Italy', emoji: '🇮🇹' },
  { city: 'London', country: 'United Kingdom', emoji: '🇬🇧' },
  { city: 'Edinburgh', country: 'United Kingdom', emoji: '🇬🇧' },
  { city: 'Manchester', country: 'United Kingdom', emoji: '🇬🇧' },
  { city: 'Liverpool', country: 'United Kingdom', emoji: '🇬🇧' },
  { city: 'Bath', country: 'United Kingdom', emoji: '🇬🇧' },
  { city: 'Berlin', country: 'Germany', emoji: '🇩🇪' },
  { city: 'Munich', country: 'Germany', emoji: '🇩🇪' },
  { city: 'Hamburg', country: 'Germany', emoji: '🇩🇪' },
  { city: 'Frankfurt', country: 'Germany', emoji: '🇩🇪' },
  { city: 'Cologne', country: 'Germany', emoji: '🇩🇪' },
  { city: 'Amsterdam', country: 'Netherlands', emoji: '🇳🇱' },
  { city: 'Rotterdam', country: 'Netherlands', emoji: '🇳🇱' },
  { city: 'The Hague', country: 'Netherlands', emoji: '🇳🇱' },
  { city: 'Lisbon', country: 'Portugal', emoji: '🇵🇹' },
  { city: 'Porto', country: 'Portugal', emoji: '🇵🇹' },
  { city: 'Faro', country: 'Portugal', emoji: '🇵🇹' },
  { city: 'Vienna', country: 'Austria', emoji: '🇦🇹' },
  { city: 'Prague', country: 'Czech Republic', emoji: '🇨🇿' },
  { city: 'Budapest', country: 'Hungary', emoji: '🇭🇺' },
  { city: 'Warsaw', country: 'Poland', emoji: '🇵🇱' },
  { city: 'Athens', country: 'Greece', emoji: '🇬🇷' },
  { city: 'Stockholm', country: 'Sweden', emoji: '🇸🇪' },
  { city: 'Copenhagen', country: 'Denmark', emoji: '🇩�' },
  { city: 'Oslo', country: 'Norway', emoji: '🇳🇴' },
  { city: 'Helsinki', country: 'Finland', emoji: '🇫🇮' },
  { city: 'Dublin', country: 'Ireland', emoji: '🇮🇪' },
  { city: 'Reykjavik', country: 'Iceland', emoji: '🇮🇸' },
  { city: 'Zurich', country: 'Switzerland', emoji: '🇨🇭' },
  { city: 'Brussels', country: 'Belgium', emoji: '🇧🇪' },
  
  // Americas
  { city: 'Havana', country: 'Cuba', emoji: '🇨🇺' },
  { city: 'Mexico City', country: 'Mexico', emoji: '🇲🇽' },
  { city: 'Cancun', country: 'Mexico', emoji: '🇲🇽' },
  { city: 'Guadalajara', country: 'Mexico', emoji: '🇲🇽' },
  { city: 'Rio de Janeiro', country: 'Brazil', emoji: '🇧🇷' },
  { city: 'São Paulo', country: 'Brazil', emoji: '🇧🇷' },
  { city: 'Buenos Aires', country: 'Argentina', emoji: '🇦🇷' },
  { city: 'Lima', country: 'Peru', emoji: '🇵🇪' },
  { city: 'Bogota', country: 'Colombia', emoji: '🇨🇴' },
  { city: 'Santiago', country: 'Chile', emoji: '🇨🇱' },
  { city: 'Caracas', country: 'Venezuela', emoji: '🇻🇪' },
  { city: 'Quito', country: 'Ecuador', emoji: '🇪🇨' },
  { city: 'La Paz', country: 'Bolivia', emoji: '🇧🇴' },
  { city: 'Montevideo', country: 'Uruguay', emoji: '🇺🇾' },
  { city: 'San Jose', country: 'Costa Rica', emoji: '🇨🇷' },
  { city: 'Panama City', country: 'Panama', emoji: '🇵🇦' },
  { city: 'Guatemala City', country: 'Guatemala', emoji: '🇬🇹' },
  { city: 'San Salvador', country: 'El Salvador', emoji: '🇸🇻' },
  { city: 'Managua', country: 'Nicaragua', emoji: '🇳🇮' },
  { city: 'Tegucigalpa', country: 'Honduras', emoji: '🇭🇳' },
  { city: 'San Pedro Sula', country: 'Honduras', emoji: '🇭🇳' },
  { city: 'Kingston', country: 'Jamaica', emoji: '🇯🇲' },
  { city: 'Port of Spain', country: 'Trinidad and Tobago', emoji: '🇹🇹' },
  { city: 'Georgetown', country: 'Guyana', emoji: '🇬🇾' },
  { city: 'Paramaribo', country: 'Suriname', emoji: '🇸🇷' },
  { city: 'Cayenne', country: 'French Guiana', emoji: '🇫🇷' },

  // Asia
  { city: 'Tokyo', country: 'Japan', emoji: '🇯🇵' },
  { city: 'Kyoto', country: 'Japan', emoji: '🇯🇵' },
  { city: 'Osaka', country: 'Japan', emoji: '🇯🇵' },
  { city: 'Hiroshima', country: 'Japan', emoji: '🇯🇵' },
  { city: 'Yokohama', country: 'Japan', emoji: '🇯🇵' },
  { city: 'Nara', country: 'Japan', emoji: '🇯🇵' },
  { city: 'Beijing', country: 'China', emoji: '🇨🇳' },
  { city: 'Shanghai', country: 'China', emoji: '🇨🇳' },
  { city: 'Guangzhou', country: 'China', emoji: '🇨�' },
  { city: 'Shenzhen', country: 'China', emoji: '🇨🇳' },
  { city: 'Chengdu', country: 'China', emoji: '🇨🇳' },
  { city: 'Hangzhou', country: 'China', emoji: '🇨🇳' },
  { city: 'Xian', country: 'China', emoji: '🇨🇳' },
  { city: 'Hong Kong', country: 'Hong Kong', emoji: '🇭🇰' },
  { city: 'Singapore', country: 'Singapore', emoji: '🇸🇬' },
  { city: 'Bangkok', country: 'Thailand', emoji: '��🇭' },
  { city: 'Mumbai', country: 'India', emoji: '🇮🇳' },
  { city: 'Delhi', country: 'India', emoji: '🇮🇳' },
  { city: 'Bangalore', country: 'India', emoji: '🇮🇳' },
  { city: 'Kolkata', country: 'India', emoji: '🇮🇳' },
  { city: 'Chennai', country: 'India', emoji: '🇮🇳' },
  { city: 'Jaipur', country: 'India', emoji: '🇮🇳' },
  { city: 'Seoul', country: 'South Korea', emoji: '🇰🇷' },
  { city: 'Busan', country: 'South Korea', emoji: '🇰🇷' },
  { city: 'Tokchon', country: 'North Korea', emoji: '🇰🇵' },
  { city: 'Taipei', country: 'Taiwan', emoji: '🇹🇼' },
  { city: 'Kuala Lumpur', country: 'Malaysia', emoji: '🇲🇾' },
  { city: 'Jakarta', country: 'Indonesia', emoji: '🇮�' },
  { city: 'Manila', country: 'Philippines', emoji: '🇵🇭' },
  { city: 'Ho Chi Minh City', country: 'Vietnam', emoji: '🇻��' },
  { city: 'Hanoi', country: 'Vietnam', emoji: '🇻🇳' },

  // Americas
  { city: 'New York', country: 'United States', emoji: '🇺🇸' },
  { city: 'Los Angeles', country: 'United States', emoji: '🇺🇸' },
  { city: 'Chicago', country: 'United States', emoji: '🇺🇸' },
  { city: 'San Francisco', country: 'United States', emoji: '🇺🇸' },
  { city: 'Miami', country: 'United States', emoji: '🇺🇸' },
  { city: 'New Orleans', country: 'United States', emoji: '🇺🇸' },
  { city: 'Boston', country: 'United States', emoji: '🇺🇸' },
  { city: 'Seattle', country: 'United States', emoji: '🇺🇸' },
  { city: 'Las Vegas', country: 'United States', emoji: '🇺🇸' },
  { city: 'Washington DC', country: 'United States', emoji: '🇺🇸' },
  { city: 'Toronto', country: 'Canada', emoji: '🇨🇦' },
  { city: 'Vancouver', country: 'Canada', emoji: '🇨🇦' },
  { city: 'Montreal', country: 'Canada', emoji: '🇨🇦' },
  { city: 'Calgary', country: 'Canada', emoji: '🇨🇦' },
  { city: 'Ottawa', country: 'Canada', emoji: '🇨🇦' },
  { city: 'Mexico City', country: 'Mexico', emoji: '🇲🇽' },
  { city: 'Guadalajara', country: 'Mexico', emoji: '🇲🇽' },
  { city: 'Cancún', country: 'Mexico', emoji: '🇲🇽' },
  { city: 'São Paulo', country: 'Brazil', emoji: '🇧🇷' },
  { city: 'Rio de Janeiro', country: 'Brazil', emoji: '🇧🇷' },
  { city: 'Salvador', country: 'Brazil', emoji: '🇧🇷' },
  { city: 'Brasília', country: 'Brazil', emoji: '🇧🇷' },
  { city: 'Buenos Aires', country: 'Argentina', emoji: '🇦🇷' },
  { city: 'Lima', country: 'Peru', emoji: '🇵🇪' },
  { city: 'Bogotá', country: 'Colombia', emoji: '🇨🇴' },
  { city: 'Santiago', country: 'Chile', emoji: '🇨🇱' },
  { city: 'Caracas', country: 'Venezuela', emoji: '🇻🇪' },

  // Middle East & Africa
  { city: 'Dubai', country: 'United Arab Emirates', emoji: '🇦🇪' },
  { city: 'Abu Dhabi', country: 'United Arab Emirates', emoji: '🇦🇪' },
  { city: 'Istanbul', country: 'Turkey', emoji: '🇹🇷' },
  { city: 'Ankara', country: 'Turkey', emoji: '🇹🇷' },
  { city: 'Tel Aviv', country: 'Israel', emoji: '🇮🇱' },
  { city: 'Jerusalem', country: 'Israel', emoji: '🇮🇱' },
  { city: 'Cairo', country: 'Egypt', emoji: '🇪🇬' },
  { city: 'Kampala', country: 'Uganda', emoji: '🇺🇬' },
  { city: 'Cape Town', country: 'South Africa', emoji: '🇿🇦' },
  { city: 'Johannesburg', country: 'South Africa', emoji: '🇿🇦' },
  { city: 'Marrakech', country: 'Morocco', emoji: '🇲🇦' },
  { city: 'Casablanca', country: 'Morocco', emoji: '🇲🇦' },

  // Oceania
  { city: 'Sydney', country: 'Australia', emoji: '🇦🇺' },
  { city: 'Melbourne', country: 'Australia', emoji: '🇦🇺' },
  { city: 'Brisbane', country: 'Australia', emoji: '🇦🇺' },
  { city: 'Perth', country: 'Australia', emoji: '🇦🇺' },
  { city: 'Adelaide', country: 'Australia', emoji: '🇦🇺' },
  { city: 'Gold Coast', country: 'Australia', emoji: '🇦🇺' },
  { city: 'Auckland', country: 'New Zealand', emoji: '🇳🇿' },
  { city: 'Wellington', country: 'New Zealand', emoji: '🇳🇿' },
  
  // Hidden Gems
  { city: 'Bruges', country: 'Belgium', emoji: '🇧🇪' },
  { city: 'Chefchaouen', country: 'Morocco', emoji: '🇲🇦' },
  { city: 'Hallstatt', country: 'Austria', emoji: '🇦🇹' },
  { city: 'Ravello', country: 'Italy', emoji: '🇮🇹' },
  { city: 'Colmar', country: 'France', emoji: '🇫🇷' },
  { city: 'Sintra', country: 'Portugal', emoji: '🇵🇹' },
  { city: 'Ghent', country: 'Belgium', emoji: '🇧🇪' },
  { city: 'Annecy', country: 'France', emoji: '�🇷' },
  { city: 'Kotor', country: 'Montenegro', emoji: '🇲🇪' },
  { city: 'Český Krumlov', country: 'Czech Republic', emoji: '🇨�' },
  { city: 'Rothenburg ob der Tauber', country: 'Germany', emoji: '🇩🇪' },
  { city: 'Positano', country: 'Italy', emoji: '🇮🇹' },
  { city: 'Bergen', country: 'Norway', emoji: '🇳🇴' },
  { city: 'Salzburg', country: 'Austria', emoji: '🇦🇹' },
  { city: 'Guanajuato', country: 'Mexico', emoji: '🇲🇽' }
];

const SimpleLocationSelector = ({ onLocationChange, onCityGuide }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedDestination, setSelectedDestination] = useState(null);
  const [popularCollapsed, setPopularCollapsed] = useState(true);
  const [gemsCollapsed, setGemsCollapsed] = useState(true);
  const [geonamesSuggestions, setGeonamesSuggestions] = useState([]);
  const [isLoadingGeonames, setIsLoadingGeonames] = useState(false);

  // Filter hardcoded destinations
  const filteredSuggestions = ALL_DESTINATIONS.filter(dest => 
    dest.city.toLowerCase().includes(searchQuery.toLowerCase()) ||
    dest.country.toLowerCase().includes(searchQuery.toLowerCase())
  ).slice(0, 6);

  // Combined suggestions (hardcoded + GeoNames)
  const allSuggestions = useMemo(() => {
    const hardcoded = filteredSuggestions;
    
    // Remove duplicates within GeoNames results first
    const uniqueGeonames = geonamesSuggestions.filter((gn, index, self) =>
      index === self.findIndex((g) => 
        g.city.toLowerCase() === gn.city.toLowerCase() && 
        g.country.toLowerCase() === gn.country.toLowerCase()
      )
    );
    
    // Then remove any that conflict with hardcoded results
    const finalGeonames = uniqueGeonames.filter(gn => 
      !hardcoded.some(hc => 
        hc.city.toLowerCase() === gn.city.toLowerCase() && 
        hc.country.toLowerCase() === gn.country.toLowerCase()
      )
    );
    
    return [...hardcoded, ...finalGeonames].slice(0, 8);
  }, [filteredSuggestions, geonamesSuggestions]);

  // Fetch GeoNames suggestions
  const fetchGeonamesSuggestions = useCallback(async (query) => {
    if (query.length < 2) {
      setGeonamesSuggestions([]);
      return;
    }

    setIsLoadingGeonames(true);
    try {
      const response = await fetch('/api/geonames-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      
      if (response.ok) {
        const data = await response.json();
        setGeonamesSuggestions(data.suggestions || []);
      }
    } catch (error) {
      console.error('GeoNames search failed:', error);
      setGeonamesSuggestions([]);
    } finally {
      setIsLoadingGeonames(false);
    }
  }, []);

  // Debounced search
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchQuery.length >= 2) {
        fetchGeonamesSuggestions(searchQuery);
      } else {
        setGeonamesSuggestions([]);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchQuery, fetchGeonamesSuggestions]);

  const handleSelect = useCallback((destination) => {
    setSelectedDestination(destination);
    setSearchQuery(`${destination.neighborhood || destination.city}, ${destination.country}`);
    setShowSuggestions(false);
    
    onLocationChange({
      country: destination.country,
      countryName: destination.country,
      city: destination.city,
      cityName: destination.city,
      state: '',
      stateName: '',
      neighborhood: destination.neighborhood || '',
      neighborhoodName: destination.neighborhood || '',
      intent: ''
    });

    // Don't auto-open Marco chat - let user intentionally click a category tab first
    // This reduces API calls from casual browsers and reserves Marco for serious users
  }, [onLocationChange]);

  return (
    <div className="simple-location-selector">
      <div className="search-section">
        <h2>Where would you like to explore?</h2>
        <div className="search-container">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setShowSuggestions(e.target.value.length > 0);
            }}
            onFocus={() => setShowSuggestions(searchQuery.length > 0)}
            placeholder="Search for a city..."
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

        {showSuggestions && allSuggestions.length > 0 && (
          <div className="suggestions-dropdown">
            {allSuggestions.map((dest, index) => (
              <div
                key={`${dest.city}-${dest.source || 'hardcoded'}-${index}`}
                className={`suggestion-item ${dest.source === 'geonames' ? 'geonames-result' : ''}`}
                onClick={() => handleSelect(dest)}
              >
                <span className="flag" data-country={dest.country}>{dest.emoji}</span>
                <div className="destination-info" aria-label={`Select ${dest.city}, ${dest.country}`}>
                  <span className="city-name">{dest.city}</span>{' '}
                  <span className="country-name">
                    {dest.state ? `${dest.state}, ${dest.country}` : dest.country}
                  </span>
                  {dest.source === 'geonames' && (
                    <span className="geonames-badge">🌍</span>
                  )}
                </div>
              </div>
            ))}
            {isLoadingGeonames && (
              <div className="loading-geonames">
                <span className="loading-text">Searching worldwide...</span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className={`popular-section ${popularCollapsed ? 'collapsed' : 'expanded'}`}>
        <div className="collapsible-header">
          <h3>Popular Destinations</h3>
          <button
            className="collapse-button"
            onClick={() => setPopularCollapsed((prev) => !prev)}
            aria-expanded={!popularCollapsed}
          >
            {popularCollapsed ? 'Show Cities' : 'Hide Cities'}
          </button>
        </div>
        {!popularCollapsed && (
          <div className="popular-grid">
            {POPULAR_DESTINATIONS.map((dest) => (
              <button
                key={`popular-${dest.city}`}
                className="popular-card"
                onClick={() => handleSelect(dest)}
              >
                <span className="flag" data-country={dest.country}>{dest.emoji}</span>
                <span className="city-name">{dest.city}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className={`gems-section ${gemsCollapsed ? 'collapsed' : 'expanded'}`}>
        <div className="collapsible-header">
          <h3>✨ Hidden Gems</h3>
          <button
            className="collapse-button"
            onClick={() => setGemsCollapsed((prev) => !prev)}
            aria-expanded={!gemsCollapsed}
          >
            {gemsCollapsed ? 'Show Gems' : 'Hide Gems'}
          </button>
        </div>

        {!gemsCollapsed && (
          <div className="gems-grid">
            {HIDDEN_GEMS.map((dest, index) => (
              <div
                key={`gem-${dest.city}-${dest.neighborhood || index}`}
                className="gem-card"
                style={{ animationDelay: `${index * 50}ms` }}
                onClick={() => handleSelect(dest)}
                title={dest.description}
              >
                <span className="flag" data-country={dest.country}>{dest.emoji}</span>
                <span className="city-name">{dest.neighborhood || dest.city}</span>
                <span className="gem-description">{dest.description}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedDestination && (
        <div className="selected-display">
          <span>Selected: {selectedDestination.emoji} {selectedDestination.city}</span>
        </div>
      )}
    </div>
  );
};

export default SimpleLocationSelector;
