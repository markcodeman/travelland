import React, { useState, useEffect } from 'react';

const API_BASE = 'http://localhost:5010';

const LocationSelector = ({ onLocationChange }) => {
  const [countries, setCountries] = useState([]);
  const [states, setStates] = useState([]);
  const [cities, setCities] = useState([]);
  const [neighborhoods, setNeighborhoods] = useState([]);

  const [selectedCountry, setSelectedCountry] = useState('');
  const [selectedState, setSelectedState] = useState('');
  const [selectedCity, setSelectedCity] = useState('');
  const [selectedNeighborhood, setSelectedNeighborhood] = useState('');

  const [loading, setLoading] = useState({
    countries: false,
    states: false,
    cities: false,
    neighborhoods: false
  });

  // Fetch countries on mount
  useEffect(() => {
    const fetchCountries = async () => {
      setLoading(prev => ({ ...prev, countries: true }));
      try {
        const response = await fetch(`${API_BASE}/api/locations/countries`);
        const data = await response.json();
        console.log('Countries data:', data);
        setCountries(data);
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
  }, [selectedCountry, selectedState, selectedCity, selectedNeighborhood, countries, states, onLocationChange]);

  const handleCountryChange = (e) => {
    const countryCode = e.target.value;
    setSelectedCountry(countryCode);
    setSelectedState('');
    setSelectedCity('');
    setSelectedNeighborhood('');
  };

  const handleStateChange = (e) => {
    const stateCode = e.target.value;
    setSelectedState(stateCode);
    setSelectedCity('');
    setSelectedNeighborhood('');
  };

  const handleCityChange = (e) => {
    const cityName = e.target.value;
    setSelectedCity(cityName);
    setSelectedNeighborhood('');
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
    <div style={{ marginBottom: '16px' }}>
      <div style={{ marginBottom: '8px' }}>
        <label style={labelStyle}>Country:</label>
        <select
          value={selectedCountry}
          onChange={handleCountryChange}
          style={selectStyle}
          disabled={loading.countries}
        >
          <option value="">
            {loading.countries ? 'Loading countries...' : 'Select a country'}
          </option>
          {countries.map(country => (
            <option key={country.code} value={country.code}>
              {country.name}
            </option>
          ))}
        </select>
      </div>

      {selectedCountry && (
        <div style={{ marginBottom: '8px' }}>
          <label style={labelStyle}>State/Province:</label>
          <select
            value={selectedState}
            onChange={handleStateChange}
            style={selectStyle}
            disabled={loading.states}
          >
            <option value="">
              {loading.states ? 'Loading states...' : 'Select a state/province'}
            </option>
            {states.map(state => (
              <option key={state.code} value={state.code}>
                {state.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {selectedState && (
        <div style={{ marginBottom: '8px' }}>
          <label style={labelStyle}>City:</label>
          <select
            value={selectedCity}
            onChange={handleCityChange}
            style={selectStyle}
            disabled={loading.cities}
          >
            <option value="">
              {loading.cities ? 'Loading cities...' : 'Select a city'}
            </option>
            {cities.map(city => (
              <option key={city.id} value={city.name}>
                {city.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {selectedCity && (
        <div style={{ marginBottom: '8px' }}>
          <label style={labelStyle}>Neighborhood (optional):</label>
          <select
            value={selectedNeighborhood}
            onChange={handleNeighborhoodChange}
            style={selectStyle}
            disabled={loading.neighborhoods}
          >
            <option value="">
              {loading.neighborhoods ? 'Loading neighborhoods...' : 'Any neighborhood'}
            </option>
            {neighborhoods.map(neighborhood => (
              <option key={neighborhood.id} value={neighborhood.name}>
                {neighborhood.name}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
};

export default LocationSelector;