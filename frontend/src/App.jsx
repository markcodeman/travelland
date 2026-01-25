import React, { useState, useEffect, useCallback, useMemo } from 'react';
import './styles/app.css';
import AutocompleteInput from './components/AutocompleteInput';
import WeatherDisplay from './components/WeatherDisplay';
import SearchResults from './components/SearchResults';
import Header from './components/Header';
import SuggestionChips from './components/SuggestionChips';
import MarcoChat from './components/MarcoChat';
import LocationSelector from './components/LocationSelector';

// Constants moved outside component to avoid recreation
const CITY_LIST = ['Rio de Janeiro', 'London', 'New York', 'Lisbon'];
const COUNTRIES = ['USA', 'Mexico', 'Spain', 'UK', 'France', 'Germany', 'Italy', 'Canada', 'Australia', 'Japan', 'China', 'India', 'Brazil', 'Argentina', 'South Africa', 'Netherlands', 'Portugal', 'Sweden', 'Norway', 'Denmark', 'Iceland'];

// Reduced popular cities list
const POPULAR_CITIES = ['New York', 'London', 'Paris', 'Tokyo', 'Sydney', 'Rio de Janeiro', 'Lisbon', 'Reykjavik', 'Berlin', 'Rome', 'Barcelona', 'Amsterdam', 'Vienna', 'Prague', 'Budapest'];

// Moved to constant to avoid recreation
const NEIGHBORHOOD_FALLBACKS = {
  'Rio de Janeiro': ['Copacabana', 'Ipanema', 'Leblon', 'Santa Teresa', 'Barra da Tijuca', 'Lapa', 'Botafogo', 'Jardim Botânico', 'Gamboa', 'Leme', 'Vidigal'],
  'London': ['Camden', 'Chelsea', 'Greenwich', 'Soho', 'Shoreditch'],
  'New York': ['Manhattan', 'Brooklyn', 'Harlem', 'Queens', 'Bronx'],
  'Lisbon': ['Baixa', 'Chiado', 'Alfama', 'Bairro Alto', 'Belém'],
  'Reykjavik': ['Miðborg', 'Vesturbær', 'Hlíðar', 'Laugardalur', 'Háaleiti']
};

const SUGGESTION_MAP = {
  transport: 'Public transport',
  hidden: 'Hidden gems',
  coffee: 'Coffee & tea',
};

// API base URL as constant (use Vite proxy by keeping this empty)
const API_BASE = '';

function App() {
  const [location, setLocation] = useState({
    country: 'MX',
    state: '',
    city: 'Tlaquepaque',
    neighborhood: '',
    countryName: 'Mexico',
    stateName: '',
    cityName: 'Tlaquepaque',
    neighborhoodName: ''
  });
  const [neighborhoodOptions, setNeighborhoodOptions] = useState([]);
  const [category, setCategory] = useState('');
  const [generating, setGenerating] = useState(false);
  const [weather, setWeather] = useState(null);
  const [weatherError, setWeatherError] = useState(null);
  const [results, setResults] = useState(null);
  const [synthResults, setSynthResults] = useState(null);
  const [synthLoading, setSynthLoading] = useState(false);
  const [synthError, setSynthError] = useState(null);
  const [selectedSuggestion, setSelectedSuggestion] = useState('');
  const [marcoOpen, setMarcoOpen] = useState(false);
  const [marcoWebRAG, setMarcoWebRAG] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');

  // Memoized API call functions
  const fetchAPI = useCallback(async (endpoint, options = {}) => {
    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options
      });
      if (!response.ok) throw new Error(`API Error: ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error(`API call to ${endpoint} failed:`, error);
      throw error;
    }
  }, []);

  // Consolidated fetch neighborhoods function
  const fetchNeighborhoods = useCallback(async (cityName, useFallback = true) => {
    if (!cityName) return [];

    // Always try both city and coordinate-based for Tlaquepaque
    if (cityName.toLowerCase() === 'tlaquepaque') {
      const lat = 20.58775;
      const lon = -103.30449;
      let cityData = [];
      let coordData = [];
      try {
        const data = await fetchAPI(`/neighborhoods?city=${encodeURIComponent(cityName)}&lang=en`);
        if (data?.neighborhoods?.length > 0) {
          cityData = data.neighborhoods.map(n => n.name || n.display_name || n.label || n.id).filter(Boolean);
        }
      } catch {}
      try {
        const data = await fetchAPI(`/neighborhoods?lat=${lat}&lon=${lon}&lang=en`);
        if (data?.neighborhoods?.length > 0) {
          coordData = data.neighborhoods.map(n => n.name || n.display_name || n.label || n.id).filter(Boolean);
        }
      } catch {}
      const fallbackNames = NEIGHBORHOOD_FALLBACKS[cityName] || [];
      // Merge and deduplicate
      return Array.from(new Set([...cityData, ...coordData, ...fallbackNames]));
    }

    try {
      // First try fetching by city name
      const data = await fetchAPI(`/neighborhoods?city=${encodeURIComponent(cityName)}&lang=en`);
      if (data?.neighborhoods?.length > 0) {
        const names = data.neighborhoods.map(n => n.name || n.display_name || n.label || n.id).filter(Boolean);
        const uniqueNames = Array.from(new Set(names));
        const fallbackNames = NEIGHBORHOOD_FALLBACKS[cityName] || [];
        return Array.from(new Set([...uniqueNames, ...fallbackNames]));
      }
      // If city-based fetch failed or returned no results, try geocoding to get coordinates
      try {
        const geoData = await fetchAPI('/geocode', {
          method: 'POST',
          body: JSON.stringify({ city: cityName })
        });
        const lat = geoData?.lat ?? geoData?.latitude;
        const lon = geoData?.lon ?? geoData?.longitude ?? geoData?.lng;
        if (lat && lon) {
          // Try fetching by coordinates
          const coordData = await fetchAPI(`/neighborhoods?lat=${lat}&lon=${lon}&lang=en`);
          if (coordData?.neighborhoods?.length > 0) {
            const names = coordData.neighborhoods.map(n => n.name || n.display_name || n.label || n.id).filter(Boolean);
            const uniqueNames = Array.from(new Set(names));
            const fallbackNames = NEIGHBORHOOD_FALLBACKS[cityName] || [];
            return Array.from(new Set([...uniqueNames, ...fallbackNames]));
          }
        }
      } catch (geoErr) {
        // Continue to fallback
      }
    } catch (err) {
      // Continue to fallback
    }
    return useFallback ? NEIGHBORHOOD_FALLBACKS[cityName] || [] : [];
  }, [fetchAPI]);

  // Auto-load Tlaquepaque neighborhoods on mount
  useEffect(() => {
    const autoLoadNeighborhoods = async () => {
      const neighborhoods = await fetchNeighborhoods('Tlaquepaque');
      setNeighborhoodOptions(neighborhoods);
    };
    
    autoLoadNeighborhoods();
  }, []); // Empty dependency array - runs once on mount

  // Fetch neighborhoods effect
  useEffect(() => {
    let mounted = true;
    
    const updateNeighborhoods = async () => {
      setNeighborhoodOptions([]);
      if (!location.city) return;
      
      const neighborhoods = await fetchNeighborhoods(location.city);
      if (mounted) {
        setNeighborhoodOptions(neighborhoods);
      }
    };
    
    updateNeighborhoods();
    return () => { mounted = false; };
  }, [location.city, fetchNeighborhoods]);

  // Consolidated quick guide fetch
  const fetchQuickGuide = useCallback(async (searchParams) => {
    try {
      return await fetchAPI('/search', {
        method: 'POST',
        body: JSON.stringify(searchParams)
      });
    } catch (error) {
      return null;
    }
  }, [fetchAPI]);

  // Quick guide effect
  useEffect(() => {
    let mounted = true;
    
    const getQuickGuide = async () => {
      if (!location.city) return;
      
      const data = await fetchQuickGuide({ query: location.city });
      if (mounted && data?.quick_guide) {
        setResults(data);
      }
    };
    
    getQuickGuide();
    return () => { mounted = false; };
  }, [location.city, fetchQuickGuide]);

  // Neighborhood-scoped quick guide effect
  useEffect(() => {
    let mounted = true;
    let timeoutId;

    const generateGuide = async () => {
      if (!location.city || !location.neighborhood) return;
      
      try {
        setGenerating(true);
        const data = await fetchAPI('/generate_quick_guide', {
          method: 'POST',
          body: JSON.stringify({ city: location.city, neighborhood: location.neighborhood })
        });
        
        if (mounted && data?.quick_guide && !category) {
          setResults({
            quick_guide: data.quick_guide,
            source: data.source,
            cached: data.cached,
            source_url: data.source_url,
            ...(data.mapillary_images && { mapillary_images: data.mapillary_images })
          });
        }
      } catch (err) {
        console.error('Generate quick guide failed', err);
      } finally {
        if (mounted) setGenerating(false);
      }
    };

    timeoutId = setTimeout(generateGuide, 250);
    return () => { 
      mounted = false; 
      clearTimeout(timeoutId); 
    };
  }, [location.city, location.neighborhood, category, fetchAPI]);

  // Weather fetch with geocoding
  const fetchWeatherData = useCallback(async (cityName, neighborhoodName = '') => {
    setWeather(null);
    setWeatherError(null);
    
    if (!cityName) return;

    try {
      // Geocode first
      const geoData = await fetchAPI('/geocode', {
        method: 'POST',
        body: JSON.stringify({ city: cityName, neighborhood: neighborhoodName })
      });

      if (geoData.display_name) {
        const parts = geoData.display_name.split(', ');
        setLocation(prev => ({ ...prev, country: parts[parts.length - 1] }));
      }

      const lat = geoData?.lat ?? geoData?.latitude;
      const lon = geoData?.lon ?? geoData?.longitude ?? geoData?.lng;
      
      if (!lat || !lon) {
        setWeatherError('Could not find coordinates for this location.');
        return;
      }

      // Fetch weather with coordinates
      const weatherData = await fetchAPI('/weather', {
        method: 'POST',
        body: JSON.stringify({ lat: Number(lat), lon: Number(lon) })
      });

      if (weatherData?.weather) {
        setWeather(weatherData.weather);
      } else {
        setWeatherError('No weather data available for this location.');
      }
    } catch (err) {
      setWeatherError('Failed to fetch weather. Check your connection or try again.');
    }
  }, [fetchAPI]);

  // Weather effect
  useEffect(() => {
    fetchWeatherData(location.city, location.neighborhood);
  }, [location.city, location.neighborhood, fetchWeatherData]);


  // Main search function - defined with useCallback to avoid recreation
  const handleSearch = useCallback(async (overrideCategory = null) => {
    if (!location.city?.trim()) {
      setWeatherError('Please select a city before searching.');
      return;
    }

    const displayCategory = overrideCategory || category;
    const message = location.neighborhood 
      ? `Finding ${displayCategory || 'great spots'} in ${location.neighborhood}, ${location.city}...`
      : `Finding ${displayCategory || 'great spots'} in ${location.city}...`;
    
    setLoadingMessage(message);
    setLoading(true);
    setWeatherError(null);

    try {
      // Parallel API calls for better performance
      const [geoData, quickGuideData] = await Promise.all([
        fetchAPI('/geocode', {
          method: 'POST',
          body: JSON.stringify({ city: location.city, neighborhood: '', country: location.country })
        }).catch(() => null),
        
        fetchQuickGuide({
          query: location.city,
          ...(location.neighborhood && { neighborhood: location.neighborhood }),
          ...(displayCategory && { category: displayCategory })
        })
      ]);

      // Update country from geocode
      if (geoData?.display_name) {
        const parts = geoData.display_name.split(', ');
        setLocation(prev => ({ ...prev, country: parts[parts.length - 1] }));
      }

      // Update neighborhoods if we have coordinates
      if (geoData?.lat && geoData?.lon) {
        try {
          const neighborhoodData = await fetchNeighborhoods(location.city, false);
          if (neighborhoodData.length > 0) {
            setNeighborhoodOptions(neighborhoodData);
          }
        } catch (err) {
          // Silently fail - we already have fallbacks
        }
      }

      // Fetch weather if we have coordinates
      if (geoData?.lat && geoData?.lon) {
        await fetchWeatherData(location.city, location.neighborhood);
      }

      // Set results from quick guide
      if (quickGuideData) {
        setResults(quickGuideData);

        // Start synthesis in background
        if (quickGuideData.quick_guide || quickGuideData.summary) {
          setSynthLoading(true);
          fetchAPI('/synthesize', {
            method: 'POST',
            body: JSON.stringify({ search_result: quickGuideData })
          })
            .then(synthData => {
              if (synthData?.synthesized_venues) {
                setSynthResults(synthData.synthesized_venues);
                setResults(prev => ({ 
                  ...prev, 
                  synthesized_venues: synthData.synthesized_venues 
                }));
              }
            })
            .catch(() => setSynthError('Marco synthesis unavailable'))
            .finally(() => setSynthLoading(false));
        }
      }
    } catch (error) {
      setWeatherError('Search failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [location.city, location.neighborhood, location.country, category, fetchAPI, fetchQuickGuide, fetchNeighborhoods, fetchWeatherData]);

  // Memoized suggestion handler with toggle behavior
  const handleSuggestion = useCallback(async (id) => {
    // Toggle: deselect if already selected
    if (selectedSuggestion === id) {
      setCategory('');
      setSelectedSuggestion('');
      // trigger a broad search with no specific category
      if (location.city) await handleSearch('');
      return;
    }

    const label = SUGGESTION_MAP[id] || id; // human label
    setCategory(id); // keep internal id
    setSelectedSuggestion(id);
    
    if (location.city) {
      await handleSearch(label); // pass label so backend gets "Hidden gems"
    }
  }, [location.city, handleSearch, selectedSuggestion]);

  // Memoized generate function
  const generateQuickGuide = useCallback(async () => {
    if (!location.city || !location.neighborhood) return;
    
    setGenerating(true);
    try {
      const data = await fetchAPI('/generate_quick_guide', {
        method: 'POST',
        body: JSON.stringify({ city: location.city, neighborhood: location.neighborhood })
      });
      
      if (data?.quick_guide) {
        setResults({ 
          quick_guide: data.quick_guide, 
          source: data.source, 
          cached: data.cached 
        });
      }
    } catch (err) {
      console.error('Generate quick guide failed', err);
    } finally {
      setGenerating(false);
    }
  }, [location.city, location.neighborhood, fetchAPI]);

  // Memoized component values
  const weatherDisplayProps = useMemo(() => ({
    weather,
    city: location.city
  }), [weather, location.city]);

  return (
    <div>
      <Header city={location.city} neighborhood={location.neighborhood} />
      
      <div style={{ minWidth: 220, margin: '0 auto', maxWidth: 600 }}>
        <WeatherDisplay {...weatherDisplayProps} />
        {weatherError && (
          <div style={{ marginTop: 8, color: '#9b2c2c', fontSize: 13 }}>
            {weatherError}
          </div>
        )}
      </div>

      <div className="app-container">
        <LocationSelector onLocationChange={setLocation} initialLocation={location} />

        {location.city && location.neighborhood && generating && (
          <div style={{ margin: '8px 0 12px 0', color: '#3b556f' }}>
            Generating quick guide…
          </div>
        )}

        <SuggestionChips onSelect={handleSuggestion} city={location.city} selected={selectedSuggestion} />
        

        <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
          <button
            disabled={!location.city}
            onClick={() => setMarcoOpen(true)}
            style={{
              padding: '12px 24px',
              background: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: 'bold'
            }}
          >
            🗺️ Explore with Marco
          </button>
        </div>

        {marcoOpen && (
          <MarcoChat
            city={location.city}
            neighborhood={location.neighborhood}
            venues={results?.venues?.slice(0, 6) || []}
            category={SUGGESTION_MAP[selectedSuggestion] || (typeof category === 'string' ? category : '')}
            initialInput={SUGGESTION_MAP[selectedSuggestion] || ''}
            wikivoyage={results?.wikivoyage}
            onClose={() => setMarcoOpen(false)}
          />
        )}
        
        <SearchResults results={results} />
      </div>
    </div>
  );
}

export default App;
