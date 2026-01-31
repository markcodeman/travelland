import React, { useState, useEffect, useRef } from 'react';
import './MagicalLocationSelector.css';

const COUNTRIES = [
  { code: 'FR', name: 'France', emoji: '🇫🇷' },
  { code: 'JP', name: 'Japan', emoji: '🇯🇵' },
  { code: 'ES', name: 'Spain', emoji: '🇪🇸' },
  { code: 'UK', name: 'United Kingdom', emoji: '🇬🇧' },
  { code: 'US', name: 'United States', emoji: '🇺🇸' },
  { code: 'IT', name: 'Italy', emoji: '🇮🇹' },
  { code: 'DE', name: 'Germany', emoji: '🇩🇪' },
  { code: 'NL', name: 'Netherlands', emoji: '🇳🇱' },
  { code: 'PT', name: 'Portugal', emoji: '🇵🇹' },
  { code: 'SE', name: 'Sweden', emoji: '🇸🇪' },
  { code: 'NO', name: 'Norway', emoji: '🇳🇴' },
  { code: 'DK', name: 'Denmark', emoji: '🇩🇰' },
  { code: 'IS', name: 'Iceland', emoji: '🇮🇸' },
  { code: 'CA', name: 'Canada', emoji: '🇨🇦' },
  { code: 'AU', name: 'Australia', emoji: '🇦🇺' },
  { code: 'CN', name: 'China', emoji: '🇨🇳' },
  { code: 'IN', name: 'India', emoji: '🇮🇳' },
  { code: 'BR', name: 'Brazil', emoji: '🇧🇷' },
  { code: 'AR', name: 'Argentina', emoji: '🇦🇷' },
  { code: 'ZA', name: 'South Africa', emoji: '🇿🇦' },
  { code: 'MX', name: 'Mexico', emoji: '🇲🇽' }
];

const CITY_DATA = {
  'FR': [
    { name: 'Paris', emoji: '🗼', sparkle: '✨' },
    { name: 'Lyon', emoji: '🦁', sparkle: '✨' },
    { name: 'Marseille', emoji: '⚓', sparkle: '✨' },
    { name: 'Nice', emoji: '🌊', sparkle: '✨' },
    { name: 'Bordeaux', emoji: '🍷', sparkle: '✨' },
    { name: 'Strasbourg', emoji: '🏰', sparkle: '✨' }
  ],
  'JP': [
    { name: 'Tokyo', emoji: '🗼', sparkle: '✨' },
    { name: 'Kyoto', emoji: '⛩️', sparkle: '✨' },
    { name: 'Osaka', emoji: '🍜', sparkle: '✨' },
    { name: 'Hiroshima', emoji: '🕊️', sparkle: '✨' },
    { name: 'Yokohama', emoji: '🚢', sparkle: '✨' },
    { name: 'Nara', emoji: '🦌', sparkle: '✨' }
  ],
  'ES': [
    { name: 'Barcelona', emoji: '🏖️', sparkle: '✨' },
    { name: 'Madrid', emoji: '👑', sparkle: '✨' },
    { name: 'Seville', emoji: '💃', sparkle: '✨' },
    { name: 'Valencia', emoji: '🍊', sparkle: '✨' },
    { name: 'Granada', emoji: '🏰', sparkle: '✨' },
    { name: 'Bilbao', emoji: '🎨', sparkle: '✨' }
  ],
  'UK': [
    { name: 'London', emoji: '🎡', sparkle: '✨' },
    { name: 'Edinburgh', emoji: '🏰', sparkle: '✨' },
    { name: 'Manchester', emoji: '🏭', sparkle: '✨' },
    { name: 'Liverpool', emoji: '🎸', sparkle: '✨' },
    { name: 'Bath', emoji: '🛁', sparkle: '✨' },
    { name: 'Oxford', emoji: '🎓', sparkle: '✨' }
  ],
  'US': [
    { name: 'New York', emoji: '🗽', sparkle: '✨' },
    { name: 'Los Angeles', emoji: '🌴', sparkle: '✨' },
    { name: 'Chicago', emoji: '🏙️', sparkle: '✨' },
    { name: 'San Francisco', emoji: '🌉', sparkle: '✨' },
    { name: 'Miami', emoji: '🏖️', sparkle: '✨' },
    { name: 'New Orleans', emoji: '🎷', sparkle: '✨' }
  ],
  'IT': [
    { name: 'Rome', emoji: '🏛️', sparkle: '✨' },
    { name: 'Venice', emoji: '🚤', sparkle: '✨' },
    { name: 'Florence', emoji: '🎨', sparkle: '✨' },
    { name: 'Milan', emoji: '👗', sparkle: '✨' },
    { name: 'Naples', emoji: '🍕', sparkle: '✨' },
    { name: 'Verona', emoji: '💕', sparkle: '✨' }
  ],
  'DE': [
    { name: 'Berlin', emoji: '🐻', sparkle: '✨' },
    { name: 'Munich', emoji: '🍺', sparkle: '✨' },
    { name: 'Hamburg', emoji: '⚓', sparkle: '✨' },
    { name: 'Frankfurt', emoji: '🏦', sparkle: '✨' },
    { name: 'Cologne', emoji: '⛪', sparkle: '✨' },
    { name: 'Dresden', emoji: '🎭', sparkle: '✨' }
  ],
  'NL': [
    { name: 'Amsterdam', emoji: '🚲', sparkle: '✨' },
    { name: 'Rotterdam', emoji: '🏢', sparkle: '✨' },
    { name: 'The Hague', emoji: '⚖️', sparkle: '✨' },
    { name: 'Utrecht', emoji: '🌷', sparkle: '✨' },
    { name: 'Eindhoven', emoji: '💡', sparkle: '✨' },
    { name: 'Maastricht', emoji: '🏰', sparkle: '✨' }
  ],
  'PT': [
    { name: 'Lisbon', emoji: '🗼', sparkle: '✨' },
    { name: 'Porto', emoji: '🍷', sparkle: '✨' },
    { name: 'Faro', emoji: '🌊', sparkle: '✨' },
    { name: 'Coimbra', emoji: '🎓', sparkle: '✨' },
    { name: 'Braga', emoji: '⛪', sparkle: '✨' },
    { name: 'Madeira', emoji: '🌺', sparkle: '✨' }
  ],
  'SE': [
    { name: 'Stockholm', emoji: '👑', sparkle: '✨' },
    { name: 'Gothenburg', emoji: '🚢', sparkle: '✨' },
    { name: 'Malmö', emoji: '🌉', sparkle: '✨' },
    { name: 'Uppsala', emoji: '🎓', sparkle: '✨' },
    { name: 'Visby', emoji: '🏰', sparkle: '✨' },
    { name: 'Kiruna', emoji: '🌌', sparkle: '✨' }
  ],
  'NO': [
    { name: 'Oslo', emoji: '🏛️', sparkle: '✨' },
    { name: 'Bergen', emoji: '🌧️', sparkle: '✨' },
    { name: 'Trondheim', emoji: '⛪', sparkle: '✨' },
    { name: 'Stavanger', emoji: '⛰️', sparkle: '✨' },
    { name: 'Tromsø', emoji: '🌌', sparkle: '✨' },
    { name: 'Ålesund', emoji: '🐠', sparkle: '✨' }
  ],
  'DK': [
    { name: 'Copenhagen', emoji: '👑', sparkle: '✨' },
    { name: 'Aarhus', emoji: '🌊', sparkle: '✨' },
    { name: 'Odense', emoji: '🏰', sparkle: '✨' },
    { name: 'Aalborg', emoji: '🍺', sparkle: '✨' },
    { name: 'Esbjerg', emoji: '⚓', sparkle: '✨' },
    { name: 'Roskilde', emoji: '🎵', sparkle: '✨' }
  ],
  'IS': [
    { name: 'Reykjavik', emoji: '🌋', sparkle: '✨' },
    { name: 'Akureyri', emoji: '❄️', sparkle: '✨' },
    { name: 'Keflavik', emoji: '✈️', sparkle: '✨' },
    { name: 'Vik', emoji: '🏖️', sparkle: '✨' },
    { name: 'Höfn', emoji: '🦐', sparkle: '✨' },
    { name: 'Selfoss', emoji: '💧', sparkle: '✨' }
  ],
  'CA': [
    { name: 'Toronto', emoji: '🗼', sparkle: '✨' },
    { name: 'Vancouver', emoji: '🌲', sparkle: '✨' },
    { name: 'Montreal', emoji: '🍁', sparkle: '✨' },
    { name: 'Calgary', emoji: '🤠', sparkle: '✨' },
    { name: 'Ottawa', emoji: '🏛️', sparkle: '✨' },
    { name: 'Quebec City', emoji: '🏰', sparkle: '✨' }
  ],
  'AU': [
    { name: 'Sydney', emoji: '🌉', sparkle: '✨' },
    { name: 'Melbourne', emoji: '🎨', sparkle: '✨' },
    { name: 'Brisbane', emoji: '☀️', sparkle: '✨' },
    { name: 'Perth', emoji: '🏖️', sparkle: '✨' },
    { name: 'Adelaide', emoji: '🍷', sparkle: '✨' },
    { name: 'Gold Coast', emoji: '🏄', sparkle: '✨' }
  ],
  'IN': [
    { name: 'Mumbai', emoji: '🌃', sparkle: '✨' },
    { name: 'Delhi', emoji: '🕌', sparkle: '✨' },
    { name: 'Bangalore', emoji: '💻', sparkle: '✨' },
    { name: 'Kolkata', emoji: '🚢', sparkle: '✨' },
    { name: 'Chennai', emoji: '🏖️', sparkle: '✨' },
    { name: 'Jaipur', emoji: '🏰', sparkle: '✨' }
  ],
  'BR': [
    { name: 'Rio de Janeiro', emoji: '🏖️', sparkle: '✨' },
    { name: 'São Paulo', emoji: '🌃', sparkle: '✨' },
    { name: 'Salvador', emoji: '🎨', sparkle: '✨' },
    { name: 'Brasília', emoji: '🏛️', sparkle: '✨' },
    { name: 'Fortaleza', emoji: '🌊', sparkle: '✨' },
    { name: 'Recife', emoji: '🏝️', sparkle: '✨' }
  ],
  'AR': [
    { name: 'Buenos Aires', emoji: '💃', sparkle: '✨' },
    { name: 'Córdoba', emoji: '⛪', sparkle: '✨' },
    { name: 'Rosario', emoji: '🌾', sparkle: '✨' },
    { name: 'Mendoza', emoji: '🍷', sparkle: '✨' },
    { name: 'La Plata', emoji: '🏛️', sparkle: '✨' },
    { name: 'Mar del Plata', emoji: '🏖️', sparkle: '✨' }
  ],
  'ZA': [
    { name: 'Cape Town', emoji: '🏔️', sparkle: '✨' },
    { name: 'Johannesburg', emoji: '💎', sparkle: '✨' },
    { name: 'Durban', emoji: '🏖️', sparkle: '✨' },
    { name: 'Pretoria', emoji: '🏛️', sparkle: '✨' },
    { name: 'Port Elizabeth', emoji: '🐧', sparkle: '✨' },
    { name: 'Bloemfontein', emoji: '🌺', sparkle: '✨' }
  ],
  'MX': [
    { name: 'Mexico City', emoji: '🏛️', sparkle: '✨' },
    { name: 'Guadalajara', emoji: '🌶️', sparkle: '✨' },
    { name: 'Monterrey', emoji: '🏭', sparkle: '✨' },
    { name: 'Cancún', emoji: '🏖️', sparkle: '✨' },
    { name: 'Playa del Carmen', emoji: '🌴', sparkle: '✨' },
    { name: 'Oaxaca', emoji: '🎨', sparkle: '✨' }
  ],
  'CN': [
    { name: 'Shanghai', emoji: '🥟', sparkle: '✨' },
    { name: 'Beijing', emoji: '🏯', sparkle: '✨' },
    { name: 'Hong Kong', emoji: '🌃', sparkle: '✨' },
    { name: 'Guangzhou', emoji: '🌸', sparkle: '✨' },
    { name: 'Shenzhen', emoji: '📱', sparkle: '✨' },
    { name: 'Chengdu', emoji: '🐼', sparkle: '✨' }
  ]
};

const MagicalLocationSelector = ({ onLocationChange, onCityGuide }) => {
  const [selectedCountry, setSelectedCountry] = useState('');
  const [selectedCity, setSelectedCity] = useState('');
  const [countryDropdownOpen, setCountryDropdownOpen] = useState(false);
  const [cityDropdownOpen, setCityDropdownOpen] = useState(false);
  const [sparkles, setSparkles] = useState([]);
  const [isAnimating, setIsAnimating] = useState(false);
  const countryRef = useRef(null);
  const cityRef = useRef(null);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (countryRef.current && !countryRef.current.contains(event.target)) {
        setCountryDropdownOpen(false);
      }
      if (cityRef.current && !cityRef.current.contains(event.target)) {
        setCityDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Generate sparkles
  const generateSparkles = () => {
    const newSparkles = Array.from({ length: 12 }, (_, i) => ({
      id: Date.now() + i,
      left: Math.random() * 100,
      delay: Math.random() * 0.5,
      duration: 1 + Math.random() * 0.5
    }));
    setSparkles(newSparkles);
    setTimeout(() => setSparkles([]), 2000);
  };

  // Handle country selection
  const handleCountrySelect = (country) => {
    setSelectedCountry(country);
    setSelectedCity(''); // Reset city when country changes
    setCityDropdownOpen(false);
    setCountryDropdownOpen(false);
    generateSparkles();
    setIsAnimating(true);
    setTimeout(() => setIsAnimating(false), 600);
  };

  // Handle city selection
  const handleCitySelect = (city) => {
    setSelectedCity(city);
    setCityDropdownOpen(false);
    generateSparkles();
    
    // Trigger location change
    const country = COUNTRIES.find(c => c.code === selectedCountry);
    onLocationChange({
      country: selectedCountry,
      countryName: country?.name || '',
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
    }, 800);
  };

  const availableCities = selectedCountry ? (CITY_DATA[selectedCountry] || []) : [];

  return (
    <div className="magical-location-selector">
      {/* Sparkles */}
      {sparkles.map(sparkle => (
        <div
          key={sparkle.id}
          className="sparkle"
          style={{
            left: `${sparkle.left}%`,
            animationDelay: `${sparkle.delay}s`,
            animationDuration: `${sparkle.duration}s`
          }}
        />
      ))}

      <div className="selector-row">
        {/* Country Dropdown */}
        <div className="dropdown-wrapper" ref={countryRef}>
          <label className="selector-label">🌍 Country</label>
          <button
            className={`dropdown-button ${isAnimating ? 'wand-waving' : ''}`}
            onClick={() => setCountryDropdownOpen(!countryDropdownOpen)}
          >
            {selectedCountry ? (
              <span className="selected-value">
                <span className="flag-emoji">
                  {COUNTRIES.find(c => c.code === selectedCountry)?.emoji}
                </span>
                {COUNTRIES.find(c => c.code === selectedCountry)?.name}
              </span>
            ) : (
              <span className="placeholder">Choose your destination...</span>
            )}
            <span className="dropdown-arrow">▼</span>
          </button>

          {countryDropdownOpen && (
            <div className="dropdown-menu country-menu">
              {COUNTRIES.map(country => (
                <div
                  key={country.code}
                  className="dropdown-item"
                  onClick={() => handleCountrySelect(country.code)}
                >
                  <span className="flag-emoji">{country.emoji}</span>
                  <span className="country-name">{country.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* City Dropdown */}
        <div className="dropdown-wrapper" ref={cityRef}>
          <label className="selector-label">🏙️ City</label>
          <button
            className={`dropdown-button ${!selectedCountry ? 'disabled' : ''}`}
            onClick={() => selectedCountry && setCityDropdownOpen(!cityDropdownOpen)}
            disabled={!selectedCountry}
          >
            {selectedCity ? (
              <span className="selected-value">
                <span className="city-emoji">
                  {availableCities.find(c => c.name === selectedCity)?.emoji}
                </span>
                {selectedCity}
              </span>
            ) : (
              <span className="placeholder">
                {selectedCountry ? 'Select a city...' : 'Choose country first...'}
              </span>
            )}
            <span className="dropdown-arrow">▼</span>
          </button>

          {cityDropdownOpen && (
            <div className="dropdown-menu city-menu">
              {availableCities.map(city => (
                <div
                  key={city.name}
                  className="dropdown-item"
                  onClick={() => handleCitySelect(city.name)}
                >
                  <span className="city-emoji">{city.emoji}</span>
                  <span className="city-name">{city.name}</span>
                  <span className="sparkle-indicator">{city.sparkle}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Helper text */}
      <div className="selector-helper">
        ✨ Select a country, then choose your magical destination city
      </div>
    </div>
  );
};

export default MagicalLocationSelector;
