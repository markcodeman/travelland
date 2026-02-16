import { useEffect, useState } from 'react';

// Use Vite proxy: API_BASE should be empty string for local dev
const API_BASE = '';

const LocationSelector = ({
  onLocationChange,
  initialLocation = {},
  neighborhoodOptions = [],
  neighborhoodOptIn = false,
  onToggleNeighborhood,
  onCityGuide,
  canTriggerCityGuide,
}) => {
  const [countries, setCountries] = useState([]);
  const [states, setStates] = useState([]);
  const [cities, setCities] = useState([]);
  const [neighborhoods, setNeighborhoods] = useState([]);

  const [selectedCountry, setSelectedCountry] = useState(initialLocation.country || '');
  const [selectedState, setSelectedState] = useState(initialLocation.state || '');
  const [selectedCity, setSelectedCity] = useState(initialLocation.city || '');
  const [selectedNeighborhood, setSelectedNeighborhood] = useState(initialLocation.neighborhood || '');

  const [countryInput, setCountryInput] = useState(initialLocation.countryName || initialLocation.country || '');
  const [stateInput, setStateInput] = useState(initialLocation.stateName || initialLocation.state || '');
  const [cityInput, setCityInput] = useState(initialLocation.cityName || initialLocation.city || '');
  const [neighborhoodInput, setNeighborhoodInput] = useState(initialLocation.neighborhoodName || initialLocation.neighborhood || '');

  const [showCountryDropdown, setShowCountryDropdown] = useState(false);
  const [showStateDropdown, setShowStateDropdown] = useState(false);
  const [showCityDropdown, setShowCityDropdown] = useState(false);
  const [showNeighborhoodDropdown, setShowNeighborhoodDropdown] = useState(false);

  const [loading, setLoading] = useState({
    countries: false,
    states: false,
    cities: false,
    neighborhoods: false
  });

  // Geolocation helper state
  const [geoLoading, setGeoLoading] = useState(false);
  const [geoError, setGeoError] = useState(null);
  // Whether to show an inline consent panel before prompting browser geolocation permission
  const [showGeoConsent, setShowGeoConsent] = useState(false);

  const handleUseMyLocation = () => {
    // Show the reassurance + consent panel; only request permission after explicit confirmation
    setGeoError(null);
    setShowGeoConsent(true);
  };

  const cancelUseMyLocation = () => {
    setShowGeoConsent(false);
    setGeoError(null);
  };

  const confirmUseMyLocation = () => {
    setShowGeoConsent(false);
    if (!navigator.geolocation) {
      setGeoError('Geolocation not supported in this browser.');
      return;
    }
    setGeoLoading(true);
    setGeoError(null);
    navigator.geolocation.getCurrentPosition(async (pos) => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      try {
        // Reverse lookup to get structured location info
        const r = await fetch(`${API_BASE}/reverse_lookup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lat, lon })
        });
        const data = await r.json().catch(() => null);
        if (!r.ok) {
          const msg = (data && (data.message || data.error)) ? (data.message || data.error) : 'Reverse lookup failed';
          console.error('reverse_lookup error:', data);
          setGeoError(msg);
          setGeoLoading(false);
          return;
        }

        // Country
        if (data?.countryCode) {
          setSelectedCountry(data.countryCode);
          setCountryInput(data.countryName || data.countryCode);
        } else if (!data?.cityName && !data?.neighborhoods?.length) {
          // Nothing helpful returned
          setGeoError('Reverse lookup returned no useful location info. Try again or enter your city manually.');
        } else {
          setGeoError(null);
        }

        // States: fetch list and try to match by name
        let matchedState = null;
        if (data?.countryCode && data?.stateName) {
          try {
            const sr = await fetch(`${API_BASE}/api/locations/states?countryCode=${data.countryCode}`);
            if (sr.ok) {
              const statesList = await sr.json();
              setStates(statesList);
              matchedState = statesList.find(s => s.name && s.name.toLowerCase() === data.stateName.toLowerCase());
              if (matchedState) {
                setSelectedState(matchedState.code);
                setStateInput(matchedState.name);
              } else {
                setStateInput(data.stateName);
              }
            }
          } catch (e) {
            // ignore
          }
        }

        // Cities: try to fetch cities for the matched state if available
        if (data?.cityName) {
          try {
            const stateCode = matchedState?.code || selectedState;
            if (stateCode) {
              const cr = await fetch(`${API_BASE}/api/locations/cities?countryCode=${data.countryCode}&stateCode=${stateCode}`);
              if (cr.ok) {
                const citiesList = await cr.json();
                setCities(citiesList);
                const matchedCity = citiesList.find(c => c.name && c.name.toLowerCase() === data.cityName.toLowerCase());
                if (matchedCity) {
                  setSelectedCity(matchedCity.name);
                  setCityInput(matchedCity.name);
                } else {
                  setSelectedCity(data.cityName);
                  setCityInput(data.cityName);
                }
              }
            } else {
              // No state code available, just set the city string
              setSelectedCity(data.cityName);
              setCityInput(data.cityName);
            }
          } catch (e) {
            // ignore
            setSelectedCity(data.cityName);
            setCityInput(data.cityName);
          }
        }

        // Neighborhoods: populate and auto-select first if available
        if (Array.isArray(data?.neighborhoods) && data.neighborhoods.length > 0) {
          const mapped = data.neighborhoods.map((n, index) => ({ key: index, id: n.id || n.name || n.label, name: n.name || n.display_name || n.label || n.id }));
          setNeighborhoods(mapped);
          // Auto-select top candidate
          setSelectedNeighborhood(mapped[0].name);
          setNeighborhoodInput(mapped[0].name);
        }

      } catch (err) {
        setGeoError('Failed to reverse lookup your location.');
      } finally {
        setGeoLoading(false);
      }
    }, (err) => {
      setGeoError('Permission denied or unable to get location.');
      setGeoLoading(false);
    }, { enableHighAccuracy: false, timeout: 10000 });
  }; 

  useEffect(() => {
    if (!neighborhoodOptIn) {
      setNeighborhoods([]);
      return;
    }
    if (Array.isArray(neighborhoodOptions) && neighborhoodOptions.length > 0) {
      const mapped = neighborhoodOptions.map((name, index) => ({
        key: `${name}-${index}`,
        id: name,
        name,
      }));
      setNeighborhoods(mapped);
    }
  }, [neighborhoodOptions, neighborhoodOptIn]);

  // Filtered options
  const filteredCountries = countries.filter(country =>
    country.name.toLowerCase().includes(countryInput.toLowerCase())
  );
  const filteredStates = states.filter(state =>
    state.name.toLowerCase().includes(stateInput.toLowerCase())
  );
  const filteredCities = cities.filter(city =>
    city.name.toLowerCase().includes(cityInput.toLowerCase())
  );
  const filteredNeighborhoods = neighborhoods.filter(neighborhood =>
    neighborhood.name.toLowerCase().includes(neighborhoodInput.toLowerCase())
  );

  // Extracted fetch helpers so refresh buttons can call them directly
  const fetchCountries = async () => {
    setLoading(prev => ({ ...prev, countries: true }));
    try {
      const response = await fetch(`${API_BASE}/api/countries`);
      const data = await response.json();
      setCountries(data);
      // Use initial location if provided, otherwise default to US for testing
      if (initialLocation.country) {
        const initialCountry = data.find(c => c.code === initialLocation.country || c.name === initialLocation.countryName);
        if (initialCountry) {
          setSelectedCountry(initialCountry.code);
          setCountryInput(initialCountry.name);
        }
      } else {
        // REMOVED: Don't auto-fill US, let users choose
        // const usCountry = data.find(c => c.code === 'US');
        // if (usCountry) {
        //   setSelectedCountry('US');
        //   setCountryInput(usCountry.name);
        // }
      }
    } catch (error) {
      console.error('Failed to fetch countries:', error);
    } finally {
      setLoading(prev => ({ ...prev, countries: false }));
    }
  };

  const refreshCountries = async () => {
    // Clear current country selection and dependent selections so user can pick a new country
    setSelectedCountry('');
    setCountryInput('');
    setSelectedState('');
    setStateInput('');
    setSelectedCity('');
    setCityInput('');
    setSelectedNeighborhood('');
    setNeighborhoodInput('');
    await fetchCountries();
    setShowCountryDropdown(true);
  };

  const fetchStates = async (countryCode) => {
    if (!countryCode) {
      setStates([]);
      setSelectedState('');
      return;
    }
    setLoading(prev => ({ ...prev, states: true }));
    try {
      const response = await fetch(`${API_BASE}/api/locations/states?countryCode=${countryCode}`);
      const data = await response.json();
      
      // Check if data is an array, not an error object
      if (!Array.isArray(data)) {
        console.error('States API returned non-array data:', data);
        setStates([]);
        return;
      }
      
      setStates(data);
      // Prefill with CA for testing if US is selected, or Jalisco for Mexico
      // REMOVED: Let users choose their own state
      // if (countryCode === 'US') {
      //   const caState = data.find(s => s.code === 'CA');
      //   if (caState) {
      //     setSelectedState('CA');
      //     setStateInput(caState.name);
      //   }
      // } else if (countryCode === 'MX') {
      //   const jaliscoState = data.find(s => s.name.toLowerCase().includes('jalisco'));
      //   if (jaliscoState) {
      //     setSelectedState(jaliscoState.code);
      //     setStateInput(jaliscoState.name);
      //   }
      // }
    } catch (error) {
      console.error('Failed to fetch states:', error);
    } finally {
      setLoading(prev => ({ ...prev, states: false }));
    }
  };

  const refreshStates = async () => {
    // Clear current state selection and dependent selections
    setSelectedState('');
    setStateInput('');
    setSelectedCity('');
    setCityInput('');
    setSelectedNeighborhood('');
    setNeighborhoodInput('');
    await fetchStates(selectedCountry);
    setShowStateDropdown(true);
  };

  const fetchCities = async (countryCode, stateCode) => {
    if (!countryCode || !stateCode) {
      setCities([]);
      setSelectedCity('');
      return;
    }
    setLoading(prev => ({ ...prev, cities: true }));
    try {
      const response = await fetch(`${API_BASE}/api/locations/cities?countryCode=${countryCode}&stateCode=${stateCode}`);
      const data = await response.json();
      setCities(data);
      // Prefill with San Francisco for testing if CA is selected
      // REMOVED: Let users choose their own city
      // if (stateCode === 'CA') {
      //   const sfCity = data.find(c => c.name.toLowerCase() === 'san francisco');
      //   if (sfCity) {
      //     setSelectedCity(sfCity.name);
      //     setCityInput(sfCity.name);
      //   }
      // }
    } catch (error) {
      console.error('Failed to fetch cities:', error);
    } finally {
      setLoading(prev => ({ ...prev, cities: false }));
    }
  };

  const refreshCities = async () => {
    // Clear current city selection and dependent selections
    setSelectedCity('');
    setCityInput('');
    setSelectedNeighborhood('');
    setNeighborhoodInput('');
    await fetchCities(selectedCountry, selectedState);
    setShowCityDropdown(true);
  };

  const fetchNeighborhoodsForCity = async (countryCode, cityName) => {
    if (!neighborhoodOptIn) {
      setNeighborhoods([]);
      return;
    }
    if (!countryCode || !cityName) {
      setNeighborhoods([]);
      setSelectedNeighborhood('');
      return;
    }

    setLoading(prev => ({ ...prev, neighborhoods: true }));
    try {
      // Special robust logic for Tlaquepaque
      if (cityName && cityName.toLowerCase() === 'tlaquepaque') {
        const lat = 20.58775;
        const lon = -103.30449;
        let cityData = [];
        let coordData = [];
        try {
          const resp = await fetch(`/api/neighborhoods?city=${encodeURIComponent(cityName)}&lang=en`);
          const data = await resp.json();
          if (data?.neighborhoods?.length > 0) {
            cityData = data.neighborhoods.map((n, index) => ({ key: index, id: n.id || n.name || n.label, name: n.name || n.display_name || n.label || n.id })).filter(n => n.name);
          }
        } catch {}
        try {
          const resp = await fetch(`/api/neighborhoods?lat=${lat}&lon=${lon}&lang=en`);
          const data = await resp.json();
          if (data?.neighborhoods?.length > 0) {
            coordData = data.neighborhoods.map((n, index) => ({ key: index, id: n.id || n.name || n.label, name: n.name || n.display_name || n.label || n.id })).filter(n => n.name);
          }
        } catch {}
        // Merge and dedupe by name
        const merged = [...cityData, ...coordData];
        const seen = new Set();
        const deduped = merged.filter((n, index) => {
          if (seen.has(n.name)) return false;
          seen.add(n.name);
          return true;
        }).map((n, index) => ({ ...n, key: index }));
        setNeighborhoods(deduped);
      } else {
        // Default: use legacy endpoint
        const response = await fetch(`${API_BASE}/api/locations/neighborhoods?countryCode=${countryCode}&cityName=${encodeURIComponent(cityName)}`);
        const data = await response.json();
        setNeighborhoods(data.map((n, index) => ({ ...n, key: index })));
      }
    } catch (error) {
      console.error('Failed to fetch neighborhoods:', error);
    } finally {
      setLoading(prev => ({ ...prev, neighborhoods: false }));
    }
  };

  const refreshNeighborhoods = async () => {
    // Clear current neighborhood selection so full list is shown
    setSelectedNeighborhood('');
    setNeighborhoodInput('');
    await fetchNeighborhoodsForCity(selectedCountry, selectedCity);
    setShowNeighborhoodDropdown(true);
  };

  // Fetch countries on mount
  useEffect(() => {
    fetchCountries();
  }, []);

  // Fetch states when country changes
  useEffect(() => {
    fetchStates(selectedCountry);
  }, [selectedCountry]);

  // Fetch cities when state changes
  useEffect(() => {
    fetchCities(selectedCountry, selectedState);
  }, [selectedCountry, selectedState]);

  // Fetch neighborhoods when city changes
  useEffect(() => {
    if (neighborhoodOptIn) {
      fetchNeighborhoodsForCity(selectedCountry, selectedCity);
    } else {
      setNeighborhoods([]);
    }
  }, [selectedCountry, selectedCity, neighborhoodOptIn]);

  // Notify parent of location changes
  useEffect(() => {
    const location = {
      country: selectedCountry,
      state: selectedState,
      city: selectedCity,
      neighborhood: selectedNeighborhood,
      countryName: countries.find(c => c.code === selectedCountry)?.name || '',
      stateName: states.find(s => s.code === selectedState)?.name || '',
      cityName: selectedCity,
      neighborhoodName: selectedNeighborhood
    };

    onLocationChange(location);
  }, [selectedCountry, selectedState, selectedCity, selectedNeighborhood, onLocationChange]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!event.target.closest('.location-selector')) {
        setShowCountryDropdown(false);
        setShowStateDropdown(false);
        setShowCityDropdown(false);
        setShowNeighborhoodDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleCountryInputChange = (e) => {
    const value = e.target.value;
    setCountryInput(value);
    if (!value) {
      setSelectedCountry('');
      setSelectedState('');
      setStateInput('');
      setSelectedCity('');
      setCityInput('');
      setSelectedNeighborhood('');
      setNeighborhoodInput('');
    }
    setShowCountryDropdown(true);
  };

  const handleCountrySelect = (country) => {
    setSelectedCountry(country.code);
    setCountryInput(country.name);
    setShowCountryDropdown(false);
    setSelectedState('');
    setStateInput('');
    setSelectedCity('');
    setCityInput('');
    setSelectedNeighborhood('');
    setNeighborhoodInput('');
  };

  const handleStateInputChange = (e) => {
    const value = e.target.value;
    setStateInput(value);
    if (!value) {
      setSelectedState('');
      setSelectedCity('');
      setCityInput('');
      setSelectedNeighborhood('');
      setNeighborhoodInput('');
    }
    setShowStateDropdown(true);
  };

  const handleStateSelect = (state) => {
    setSelectedState(state.code);
    setStateInput(state.name);
    setShowStateDropdown(false);
    setSelectedCity('');
    setCityInput('');
    setSelectedNeighborhood('');
    setNeighborhoodInput('');
  };

  const handleCityInputChange = (e) => {
    const value = e.target.value;
    setCityInput(value);
    setSelectedCity(value);
    if (!value) {
      setSelectedNeighborhood('');
      setNeighborhoodInput('');
    }
    setShowCityDropdown(true);
  };

  const handleCitySelect = (city) => {
    setSelectedCity(city.name);
    setCityInput(city.name);
    setShowCityDropdown(false);
    setSelectedNeighborhood('');
    setNeighborhoodInput('');
  };

  const handleNeighborhoodInputChange = (e) => {
    const value = e.target.value;
    setNeighborhoodInput(value);
    setSelectedNeighborhood(value);
    setShowNeighborhoodDropdown(true);
  };

  const handleNeighborhoodSelect = (neighborhood) => {
    setSelectedNeighborhood(neighborhood.name);
    setNeighborhoodInput(neighborhood.name);
    setShowNeighborhoodDropdown(false);
  };

  const handleNeighborhoodChange = (e) => {
    setSelectedNeighborhood(e.target.value);
  };

  const selectStyle = {
    width: '100%',
    padding: '8px',
    border: '1px solid #ccc',
    borderRadius: '4px',
    marginBottom: '8px',
    fontSize: '14px'
  };

  const labelStyle = {
    display: 'block',
    marginBottom: '4px',
    fontWeight: 'bold',
    color: '#333'
  };

  return (
    <div className="location-selector" style={{ marginBottom: '16px' }}>
      <div style={{ marginBottom: 8, textAlign: 'right' }}>
        <button type="button" aria-label="Use my location" title="Use my location" onClick={handleUseMyLocation} style={{ padding: '6px 10px', fontSize: 13, borderRadius: 6, cursor: 'pointer' }} disabled={geoLoading}>{geoLoading ? 'Locating…' : 'Use my location 📍'}</button>
        {geoError && (<div style={{ color: '#9b2c2c', marginTop: 4, fontSize: 13 }}>{geoError}</div>)}
        {showGeoConsent && (
          <div style={{ marginTop: 6, fontSize: 12, color: '#6b7280', textAlign: 'right' }} role="dialog" aria-live="polite">
            <div>Trust me — we only use your location to suggest nearby places and we don't store it. Your secret's safe with us. Opt out anytime. — Akim Meyer. What? Are you alive?</div>
            <div style={{ marginTop: 6 }}>
              <button type="button" onClick={confirmUseMyLocation} style={{ marginRight: 8, padding: '6px 10px', fontSize: 13, borderRadius: 6, cursor: 'pointer' }} disabled={geoLoading}>Yes, continue</button>
              <button type="button" onClick={cancelUseMyLocation} style={{ padding: '6px 10px', fontSize: 13, borderRadius: 6, cursor: 'pointer' }} disabled={geoLoading}>No, thanks</button>
            </div>
          </div>
        )}
      </div>

      <div style={{ marginBottom: '8px', position: 'relative' }}>
        <label style={labelStyle}>Country: <button type="button" aria-label="Refresh countries" title="Refresh countries" onClick={refreshCountries} style={{ marginLeft: 8, padding: '2px 6px', fontSize: 12, borderRadius: 4, cursor: 'pointer' }}>↻</button></label>
        <input
          type="text"
          value={countryInput}
          onChange={handleCountryInputChange}
          onFocus={() => setShowCountryDropdown(true)}
          placeholder={loading.countries ? 'Loading countries...' : 'Type to search countries'}
          style={selectStyle}
          disabled={loading.countries}
        />
        {showCountryDropdown && filteredCountries.length > 0 && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            background: 'white',
            border: '1px solid #ccc',
            borderTop: 'none',
            maxHeight: '200px',
            overflowY: 'auto',
            zIndex: 1000
          }}>
            {filteredCountries.map(country => (
              <div
                key={country.code}
                onClick={() => handleCountrySelect(country)}
                style={{
                  padding: '8px',
                  cursor: 'pointer',
                  borderBottom: '1px solid #eee'
                }}
                onMouseEnter={(e) => e.target.style.background = '#f5f5f5'}
                onMouseLeave={(e) => e.target.style.background = 'white'}
              >
                {country.name}
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedCountry && (
        <div style={{ marginBottom: '8px', position: 'relative' }}>
          <label style={labelStyle}>State/Province: <button type="button" aria-label="Refresh states" title="Refresh states" onClick={refreshStates} style={{ marginLeft: 8, padding: '2px 6px', fontSize: 12, borderRadius: 4, cursor: 'pointer' }}>↻</button></label>
          <input
            type="text"
            value={stateInput}
            onChange={handleStateInputChange}
            onFocus={() => setShowStateDropdown(true)}
            placeholder={loading.states ? 'Loading states...' : 'Type to search states'}
            style={selectStyle}
            disabled={loading.states}
          />
          {showStateDropdown && filteredStates.length > 0 && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              background: 'white',
              border: '1px solid #ccc',
              borderTop: 'none',
              maxHeight: '200px',
              overflowY: 'auto',
              zIndex: 1000
            }}>
              {filteredStates.map(state => {
                // Add US state icons for US states
                const getStateIcon = (stateName, countryCode) => {
                  if (countryCode !== 'US') return '';
                  
                  const US_STATE_ICONS = {
                    'Alabama': '🏛️', 'Alaska': '🏔️', 'Arizona': '🌵', 'Arkansas': '🌲',
                    'California': '🌴', 'Colorado': '🏔️', 'Connecticut': '⚓', 'Delaware': '🦢',
                    'Florida': '🏖️', 'Georgia': '🍑', 'Hawaii': '🌺', 'Idaho': '🥔',
                    'Illinois': '🏛️', 'Indiana': '🏀', 'Iowa': '🌽', 'Kansas': '🌾',
                    'Kentucky': '🥃', 'Louisiana': '🎷', 'Maine': '🦞', 'Maryland': '🦀',
                    'Massachusetts': '⚓', 'Michigan': '🍒', 'Minnesota': '🏒', 'Mississippi': '🦈',
                    'Missouri': '🏛️', 'Montana': '🐻', 'Nebraska': '🌽', 'Nevada': '🎰',
                    'New Hampshire': '🏔️', 'New Jersey': '🍔', 'New Mexico': '🌶️', 'New York': '🗽',
                    'North Carolina': '🍑', 'North Dakota': '🌾', 'Ohio': '🏛️', 'Oklahoma': '🌪️',
                    'Oregon': '🌲', 'Pennsylvania': '🔔', 'Rhode Island': '⚓', 'South Carolina': '🍑',
                    'South Dakota': '🏔️', 'Tennessee': '🎵', 'Texas': '🤠', 'Utah': '🏔️',
                    'Vermont': '🍁', 'Virginia': '🏛️', 'Washington': '🍎', 'West Virginia': '🏔️',
                    'Wisconsin': '🧀', 'Wyoming': '🐎', 'District of Columbia': '🏛️'
                  };
                  
                  return US_STATE_ICONS[stateName] || '';
                };
                
                return (
                  <div
                    key={state.code}
                    onClick={() => handleStateSelect(state)}
                    style={{
                      padding: '8px',
                      cursor: 'pointer',
                      borderBottom: '1px solid #eee',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                    onMouseEnter={(e) => e.target.style.background = '#f5f5f5'}
                    onMouseLeave={(e) => e.target.style.background = 'white'}
                  >
                    <span style={{ fontSize: '16px' }}>
                      {getStateIcon(state.name, selectedCountry)}
                    </span>
                    <span>{state.name}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {selectedState && (
        <div style={{ marginBottom: '8px', position: 'relative' }}>
          <label style={labelStyle}>City: <button type="button" aria-label="Refresh cities" title="Refresh cities" onClick={refreshCities} style={{ marginLeft: 8, padding: '2px 6px', fontSize: 12, borderRadius: 4, cursor: 'pointer' }}>↻</button></label>
          <input
            type="text"
            value={cityInput}
            onChange={handleCityInputChange}
            onFocus={() => setShowCityDropdown(true)}
            placeholder={loading.cities ? 'Loading cities...' : 'Type to search cities'}
            style={selectStyle}
            disabled={loading.cities}
          />
          {showCityDropdown && filteredCities.length > 0 && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              background: 'white',
              border: '1px solid #ccc',
              borderTop: 'none',
              maxHeight: '200px',
              overflowY: 'auto',
              zIndex: 1000
            }}>
              {filteredCities.map((city, index) => (
                <div
                  key={city.id || city.geonameId || `${city.name}-${index}`}
                  onClick={() => handleCitySelect(city)}
                  style={{
                    padding: '8px',
                    cursor: 'pointer',
                    borderBottom: '1px solid #eee'
                  }}
                  onMouseEnter={(e) => e.target.style.background = '#f5f5f5'}
                  onMouseLeave={(e) => e.target.style.background = 'white'}
                >
                  {city.name}
                </div>
              ))}
            </div>
          )}
          <div className="city-guide-actions">
            <button
              className="city-guide-button"
              type="button"
              onClick={onCityGuide}
              disabled={!canTriggerCityGuide}
            >
              👉 City guide
            </button>
          </div>
        </div>
      )}

      {selectedCity && !neighborhoodOptIn && onToggleNeighborhood && (
        <div className="neighborhood-optin block sm:flex items-center justify-between gap-3 p-3 bg-yellow-50 border border-yellow-200 rounded-md text-sm" role="region" aria-label="Enable neighborhoods" title="Enable neighborhoods to choose a neighborhood and get a hyper-local quick guide">
          <div className="flex items-center gap-2">
            <strong className="text-slate-800">Want a hyper-local guide?</strong>
            <span className="text-slate-600">Enable neighborhoods to pick a specific area.</span>
            <span className="ml-2 text-xs text-slate-500" title="Neighborhood suggestions are optional and cached">ℹ️</span>
          </div>
          <button
            type="button"
            onClick={onToggleNeighborhood}
            className="ml-2 rounded-full bg-brand-orange/90 text-white px-3 py-2 text-sm font-semibold shadow-sm hover:opacity-95"
            aria-expanded="false"
            aria-controls="neighborhood-input"
          >
            Enable neighborhoods
          </button>
        </div>
      )}

      {selectedCity && neighborhoodOptIn && (
        <div style={{ marginBottom: '8px', position: 'relative' }}>
          <label style={labelStyle}>
            Neighborhood (optional):
            <button type="button" aria-label="Refresh neighborhoods" title="Refresh neighborhoods" onClick={refreshNeighborhoods} style={{ marginLeft: 8, padding: '2px 6px', fontSize: 12, borderRadius: 4, cursor: 'pointer' }}>↻</button>
            <button type="button" aria-label="Use my location" title="Use my location" onClick={handleUseMyLocation} style={{ marginLeft: 8, padding: '2px 8px', fontSize: 12, borderRadius: 4, cursor: 'pointer' }} disabled={geoLoading}>{geoLoading ? 'Locating…' : 'Use my location 📍'}</button>
            {onToggleNeighborhood && (
              <button type="button" style={{ marginLeft: 8, padding: '2px 8px', fontSize: 12, borderRadius: 4, cursor: 'pointer', background: '#f5f5f5', color: '#333' }} onClick={onToggleNeighborhood}>
                Hide
              </button>
            )}
          </label>
          <input
            id="neighborhood-input"
            type="text"
            value={neighborhoodInput}
            onChange={handleNeighborhoodInputChange}
            onFocus={() => setShowNeighborhoodDropdown(true)}
            placeholder={loading.neighborhoods ? 'Loading neighborhoods...' : 'Type to search neighborhoods'}
            style={selectStyle}
            disabled={loading.neighborhoods}
          />
          <div className="neighborhood-status-wrap">
            {loading.neighborhoods ? (
              <div className="neighborhood-status neighborhood-status--loading" role="status" aria-live="polite">
                <span className="status-spinner" aria-hidden="true" />
                <span>Loading neighborhoods… pick one to unlock a hyper-local guide.</span>
              </div>
            ) : neighborhoods.length > 0 ? (
              !selectedNeighborhood && (
                <div className="neighborhood-status neighborhood-status--ready">
                  Neighborhood suggestions are ready. Choose one for a deeper quick guide.
                </div>
              )
            ) : (
              <div className="neighborhood-status neighborhood-status--empty">
                We couldn’t find neighborhoods right now—you can still explore the city guide.
              </div>
            )}
          </div>
          {showNeighborhoodDropdown && filteredNeighborhoods.length > 0 && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              background: 'white',
              border: '1px solid #ccc',
              borderTop: 'none',
              maxHeight: '200px',
              overflowY: 'auto',
              zIndex: 1000
            }}>
              {filteredNeighborhoods.map(neighborhood => (
                <div
                  key={neighborhood.id}
                  onClick={() => handleNeighborhoodSelect(neighborhood)}
                  style={{
                    padding: '8px',
                    cursor: 'pointer',
                    borderBottom: '1px solid #eee'
                  }}
                  onMouseEnter={(e) => e.target.style.background = '#f5f5f5'}
                  onMouseLeave={(e) => e.target.style.background = 'white'}
                >
                  {neighborhood.name}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default LocationSelector;