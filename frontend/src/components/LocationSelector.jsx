import React, { useState, useEffect } from 'react';

const API_BASE = '';

const LocationSelector = ({ onLocationChange }) => {
  const [countries, setCountries] = useState([]);
  const [states, setStates] = useState([]);
  const [cities, setCities] = useState([]);
  const [neighborhoods, setNeighborhoods] = useState([]);

  const [selectedCountry, setSelectedCountry] = useState('');
  const [selectedState, setSelectedState] = useState('');
  const [selectedCity, setSelectedCity] = useState('');
  const [selectedNeighborhood, setSelectedNeighborhood] = useState('');

  const [countryInput, setCountryInput] = useState('');
  const [stateInput, setStateInput] = useState('');
  const [cityInput, setCityInput] = useState('');
  const [neighborhoodInput, setNeighborhoodInput] = useState('');

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

  // Fetch countries on mount
  useEffect(() => {
    const fetchCountries = async () => {
      setLoading(prev => ({ ...prev, countries: true }));
      try {
        const response = await fetch(`${API_BASE}/api/locations/countries`);
        const data = await response.json();
        console.log('Countries data:', data);
        setCountries(data);
        // Prefill with US for testing
        const usCountry = data.find(c => c.code === 'US');
        if (usCountry) {
          setSelectedCountry('US');
          setCountryInput(usCountry.name);
        }
      } catch (error) {
        console.error('Failed to fetch countries:', error);
      } finally {
        setLoading(prev => ({ ...prev, countries: false }));
      }
    };

    fetchCountries();
  }, []);

  // Fetch states when country changes
  useEffect(() => {
    if (!selectedCountry) {
      setStates([]);
      setSelectedState('');
      return;
    }

    const fetchStates = async () => {
      setLoading(prev => ({ ...prev, states: true }));
      try {
        const response = await fetch(`${API_BASE}/api/locations/states?countryCode=${selectedCountry}`);
        const data = await response.json();
        setStates(data);
        // Prefill with CA for testing if US is selected
        if (selectedCountry === 'US') {
          const caState = data.find(s => s.code === 'CA');
          if (caState) {
            setSelectedState('CA');
            setStateInput(caState.name);
          }
        }
      } catch (error) {
        console.error('Failed to fetch states:', error);
      } finally {
        setLoading(prev => ({ ...prev, states: false }));
      }
    };

    fetchStates();
  }, [selectedCountry]);

  // Fetch cities when state changes
  useEffect(() => {
    if (!selectedCountry || !selectedState) {
      setCities([]);
      setSelectedCity('');
      return;
    }

    const fetchCities = async () => {
      setLoading(prev => ({ ...prev, cities: true }));
      try {
        const response = await fetch(`${API_BASE}/api/locations/cities?countryCode=${selectedCountry}&stateCode=${selectedState}`);
        const data = await response.json();
        setCities(data);
        // Prefill with San Francisco for testing if CA is selected
        if (selectedState === 'CA') {
          const sfCity = data.find(c => c.name.toLowerCase() === 'san francisco');
          if (sfCity) {
            setSelectedCity(sfCity.name);
            setCityInput(sfCity.name);
          }
        }
      } catch (error) {
        console.error('Failed to fetch cities:', error);
      } finally {
        setLoading(prev => ({ ...prev, cities: false }));
      }
    };

    fetchCities();
  }, [selectedCountry, selectedState]);

  // Fetch neighborhoods when city changes
  useEffect(() => {
    if (!selectedCountry || !selectedCity) {
      setNeighborhoods([]);
      setSelectedNeighborhood('');
      return;
    }

    const fetchNeighborhoods = async () => {
      setLoading(prev => ({ ...prev, neighborhoods: true }));
      try {
        const response = await fetch(`${API_BASE}/api/locations/neighborhoods?countryCode=${selectedCountry}&cityName=${encodeURIComponent(selectedCity)}`);
        const data = await response.json();
        setNeighborhoods(data);
      } catch (error) {
        console.error('Failed to fetch neighborhoods:', error);
      } finally {
        setLoading(prev => ({ ...prev, neighborhoods: false }));
      }
    };

    fetchNeighborhoods();
  }, [selectedCountry, selectedCity]);

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
      <div style={{ marginBottom: '8px', position: 'relative' }}>
        <label style={labelStyle}>Country:</label>
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
          <label style={labelStyle}>State/Province:</label>
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
              {filteredStates.map(state => (
                <div
                  key={state.code}
                  onClick={() => handleStateSelect(state)}
                  style={{
                    padding: '8px',
                    cursor: 'pointer',
                    borderBottom: '1px solid #eee'
                  }}
                  onMouseEnter={(e) => e.target.style.background = '#f5f5f5'}
                  onMouseLeave={(e) => e.target.style.background = 'white'}
                >
                  {state.name}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {selectedState && (
        <div style={{ marginBottom: '8px', position: 'relative' }}>
          <label style={labelStyle}>City:</label>
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
              {filteredCities.map(city => (
                <div
                  key={city.id}
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
        </div>
      )}

      {selectedCity && (
        <div style={{ marginBottom: '8px', position: 'relative' }}>
          <label style={labelStyle}>Neighborhood (optional):</label>
          <input
            type="text"
            value={neighborhoodInput}
            onChange={handleNeighborhoodInputChange}
            onFocus={() => setShowNeighborhoodDropdown(true)}
            placeholder={loading.neighborhoods ? 'Loading neighborhoods...' : 'Type to search neighborhoods'}
            style={selectStyle}
            disabled={loading.neighborhoods}
          />
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