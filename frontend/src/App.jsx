import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import './styles/app.css';
import AutocompleteInput from './components/AutocompleteInput';
import WeatherDisplay from './components/WeatherDisplay';
import Header from './components/Header';
import MarcoChat from './components/MarcoChat';
import SimpleLocationSelector from './components/SimpleLocationSelector';
import CitySuggestions from './components/CitySuggestions';
import NeighborhoodPicker from './components/NeighborhoodPicker';
import HeroImage from './components/HeroImage';
import SearchResults from './components/SearchResults';
import FunFact from './components/FunFact';
import { getHeroImage, getHeroImageMeta } from './services/imageService';

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

const CITY_ALIASES = {
  'khalifah a city': 'Khalifa City',
  'khalifah city': 'Khalifa City',
  'mussafah city': 'Mussafah',
  'musaffah city': 'Mussafah',
};

const buildCityFallback = (city) => {
  const name = city || 'this city';
  return `${name} is warming up on our radar. Start exploring city-wide vibes now, and pick a neighborhood to unlock hyper-local recommendations.`;
};

const generateSampleVenues = (city, intent) => {
  const intentCategories = {
    'coffee': ['Café de Flore', 'Blue Bottle Coffee', 'Starbucks Reserve', 'Local Roastery'],
    'nightlife': ['Rooftop Lounge', 'Underground Club', 'Jazz Bar', 'Dance Hall'],
    'beaches': ['Sunset Beach', 'Crystal Cove', 'Paradise Shore', 'Golden Sands'],
    'food': ['Bistro Parisien', 'Street Food Market', 'Fine Dining', 'Local Eatery'],
    'shopping': ['Boutique Gallery', 'Vintage Market', 'Designer Store', 'Local Crafts'],
    'culture': ['Art Museum', 'Historic Monument', 'Gallery District', 'Cultural Center']
  };

  const defaultVenues = [
  { name: 'City Plaza', category: 'plaza' },
  { name: 'Central Park', category: 'park' },
  { name: 'Historic District', category: 'historic' },
  { name: 'Riverside Walk', category: 'walk' }
];
  
  const category = (intent || '').toLowerCase().split(',')[0];
  const venueNames = intentCategories[category] || defaultVenues;
  
  return venueNames.map((venue, index) => {
    const name = typeof venue === 'string' ? venue : venue.name;
    const venueCategory = typeof venue === 'string' ? category || 'popular' : venue.category;
    
    return {
      id: `${city}-${index}`,
      name: name,
      category: venueCategory,
      address: `${city} District`,
      description: `Experience the best ${venueCategory} in ${city}. A must-visit destination for travelers.`,
      rating: 4.5 + Math.random() * 0.5,
      price: '$$'
    };
  });
};

const looksLikeMisalignedGuide = (text, city) => {
  if (!text || !city) return false;
  const lower = text.toLowerCase();
  const cityLower = city.toLowerCase();
  if (lower.includes(cityLower)) return false;
  const geoCues = [
    'intermittent stream',
    'well known places',
    'travel destinations',
    'af.geoview.info',
    'lat,',
    'long',
    'sar-e',
    'parmin'
  ];
  return geoCues.some(token => lower.includes(token));
};

function App() {
  const [location, setLocation] = useState({
    country: '',
    state: '',
    city: '',
    neighborhood: '',
    countryName: '',
    stateName: '',
    cityName: '',
    neighborhoodName: ''
  });
  const [neighborhoodOptions, setNeighborhoodOptions] = useState([]);
  const [neighborhoodOptIn, setNeighborhoodOptIn] = useState(false);
  const [category, setCategory] = useState('');
  const [categoryLabel, setCategoryLabel] = useState('');
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
  const [cityGuideLoading, setCityGuideLoading] = useState(false);
  const [parsedIntent, setParsedIntent] = useState('');
  const [venues, setVenues] = useState([]);
  const [heroImage, setHeroImage] = useState('');
  const [heroImageMeta, setHeroImageMeta] = useState({});
  const [showCitySuggestions, setShowCitySuggestions] = useState(false);
  const [showNeighborhoodPicker, setShowNeighborhoodPicker] = useState(false);
  const [smartNeighborhoods, setSmartNeighborhoods] = useState([]);
  const [pendingCategory, setPendingCategory] = useState(null);
  const marcoOpenTimerRef = useRef(null);

  const clearMarcoOpenTimer = useCallback(() => {
    if (marcoOpenTimerRef.current) {
      clearTimeout(marcoOpenTimerRef.current);
      marcoOpenTimerRef.current = null;
    }
  }, []);

  const scheduleMarcoOpen = useCallback(() => {
    clearMarcoOpenTimer();
    marcoOpenTimerRef.current = setTimeout(() => {
      setMarcoOpen(true);
      marcoOpenTimerRef.current = null;
    }, 1000);
  }, [clearMarcoOpenTimer]);

  useEffect(() => {
    return () => clearMarcoOpenTimer();
  }, [clearMarcoOpenTimer]);

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

  // Fetch hero image when city changes
  useEffect(() => {
    let cancelled = false;
    if (!location.city) {
      setHeroImage('');
      setHeroImageMeta({});
      return;
    }

    (async () => {
      try {
        const imageUrl = await getHeroImage(location.city, parsedIntent || categoryLabel || category);
        const imageMeta = await getHeroImageMeta(location.city, parsedIntent || categoryLabel || category);
        if (!cancelled) {
          setHeroImage(imageUrl);
          setHeroImageMeta(imageMeta);
        }
      } catch (err) {
        if (!cancelled) {
          setHeroImage('');
          setHeroImageMeta({});
        }
      }
    })();

    return () => { cancelled = true; };
  }, [location.city, parsedIntent, categoryLabel, category]);

  const normalizeCityName = useCallback((cityValue) => {
    if (!cityValue) return cityValue;
    let name = cityValue.trim();
    const aliasKey = name.toLowerCase();
    if (CITY_ALIASES[aliasKey]) {
      return CITY_ALIASES[aliasKey];
    }
    if (aliasKey.endsWith(' city')) {
      name = name.slice(0, -4).trim();
    }
    return name;
  }, []);

  // SimpleLocationSelector location change handler
  const handleSimpleLocationChange = useCallback((loc) => {
    const normalizedCity = normalizeCityName(loc.city);
    setLocation(prev => ({
      ...prev,
      ...loc,
      city: normalizedCity,
      cityName: normalizedCity,
    }));

    // Show city suggestions when a city is selected
    if (normalizedCity) {
      setShowCitySuggestions(true);
      
      // Auto-scroll to categories after city selection
      setTimeout(() => {
        const categoriesElement = document.querySelector('.city-suggestions');
        if (categoriesElement) {
          categoriesElement.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'start' 
          });
        }
      }, 100);
    }

    // Reset category selections when city changes
    setCategory('');
    setCategoryLabel('');
    setSelectedSuggestion('');

    // Store intent for visual components
    if (loc.intent) {
      setParsedIntent(loc.intent);
    }
    
    // Don't generate fake venues - wait for real API data
    if (loc.city && !venues.length) {
      setVenues([]);
    }
  }, [normalizeCityName, venues]);

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

  // Fetch smart neighborhood suggestions for large cities with a timeout
  const fetchSmartNeighborhoods = useCallback(async (city, category = '') => {
    if (!city) return { is_large_city: false, neighborhoods: [] };
    
    try {
      // Set a timeout of 15 seconds to allow backend more time to respond
      const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Timeout fetching neighborhoods')), 15000);
      });
      
      const responsePromise = fetch(`${API_BASE}/api/smart-neighborhoods?city=${encodeURIComponent(city)}&category=${encodeURIComponent(category)}`);
      
      const response = await Promise.race([responsePromise, timeoutPromise]);
      if (!response.ok) {
        console.error('Failed to fetch smart neighborhoods: HTTP error', response.status, response.statusText);
        return { is_large_city: true, neighborhoods: [] };
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch smart neighborhoods:', error.message, error.stack);
      // Fallback to any cached neighborhoods or empty list with large city flag to show picker if possible
      return { is_large_city: true, neighborhoods: [] };
    }
  }, []);

  // Fetch neighborhoods effect
  useEffect(() => {
    let mounted = true;
    
    const updateNeighborhoods = async () => {
      if (!neighborhoodOptIn) {
        setNeighborhoodOptions([]);
        return;
      }

      setNeighborhoodOptions([]);
      if (!location.city) return;
      
      const neighborhoods = await fetchNeighborhoods(location.city);
      if (mounted) {
        setNeighborhoodOptions(neighborhoods);
      }
    };
    
    updateNeighborhoods();
    return () => { mounted = false; };
  }, [location.city, fetchNeighborhoods, neighborhoodOptIn]);

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
      if (!location.city) {
        setCityGuideLoading(false);
        return;
      }

      setCityGuideLoading(true);
      try {
        const data = await fetchQuickGuide({ query: location.city, state: location.state, country: location.country, intent: location.intent });
        if (mounted && data?.quick_guide) {
          setResults(data);
        }
      } finally {
        if (mounted) setCityGuideLoading(false);
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
  const handleSearch = useCallback(async (overrideCategory = null, cityOverride = null) => {
    const searchCity = cityOverride || location.city;
    if (!searchCity?.trim()) {
      setWeatherError('Please select a city before searching.');
      return;
    }

    const displayCategory = overrideCategory || categoryLabel || category;
    const message = location.neighborhood 
      ? `Finding ${displayCategory || 'great spots'} in ${location.neighborhood}, ${searchCity}...`
      : `Finding ${displayCategory || 'great spots'} in ${searchCity}...`;
    
    setLoadingMessage(message);
    setLoading(true);
    setWeatherError(null);

    try {
      // Parallel API calls for better performance
      const [geoData, quickGuideData] = await Promise.all([
        fetchAPI('/geocode', {
          method: 'POST',
          body: JSON.stringify({ city: searchCity, neighborhood: '', country: location.country })
        }).catch(() => null),
        
        fetchQuickGuide({
          query: searchCity,
          state: location.state,
          country: location.country,
          ...(location.neighborhood && neighborhoodOptIn && { neighborhood: location.neighborhood }),
          ...(displayCategory && { category: displayCategory, intent: displayCategory })
        })
      ]);

      // Update country from geocode
      if (geoData?.display_name) {
        const parts = geoData.display_name.split(', ');
        setLocation(prev => ({ ...prev, country: parts[parts.length - 1] }));
      }

      // Update neighborhoods if we have coordinates
      if (geoData?.lat && geoData?.lon) {
        if (neighborhoodOptIn) {
          try {
            const neighborhoodData = await fetchNeighborhoods(location.city, false);
            if (neighborhoodData.length > 0) {
              setNeighborhoodOptions(neighborhoodData);
            }
          } catch (err) {
            // Silently fail - we already have fallbacks
          }
        }
      }

      // Fetch weather if we have coordinates
      if (geoData?.lat && geoData?.lon) {
        await fetchWeatherData(searchCity, location.neighborhood);
      }

      // Set results from quick guide
      if (!quickGuideData) {
        setResults({
          quick_guide: buildCityFallback(searchCity),
          source: 'fallback',
          cached: false,
        });
      } else {
        setResults(() => {
          if (quickGuideData.quick_guide) {
            if (looksLikeMisalignedGuide(quickGuideData.quick_guide, searchCity)) {
              return {
                ...quickGuideData,
                quick_guide: buildCityFallback(searchCity),
                source: 'fallback',
                cached: false,
              };
            }
            return quickGuideData;
          }
          if (quickGuideData.summary) {
            return quickGuideData;
          }
          return {
            ...quickGuideData,
            quick_guide: buildCityFallback(searchCity),
            source: 'fallback',
            cached: false,
          };
        });

        // Use real venues from search results if available
        if (quickGuideData?.venues && quickGuideData.venues.length > 0) {
          setVenues(quickGuideData.venues);
        } else if (!displayCategory && quickGuideData.quick_guide) {
          // Don't show mock venues when just browsing city guides
          setVenues([]);
        } else if (displayCategory && !venues.length && quickGuideData.quick_guide) {
          // Don't generate fake venues - wait for real API data
          setVenues([]);
        }

        // Start synthesis in background only when we have real guide text
        if (quickGuideData.quick_guide && !looksLikeMisalignedGuide(quickGuideData.quick_guide, location.city) || quickGuideData.summary) {
          setSynthLoading(true);
          fetchAPI('/synthesize', {
            method: 'POST',
            body: JSON.stringify({ search_result: quickGuideData })
          })
            .then(synthData => {
              if (synthData?.synthesized_venues) {
                setSynthResults(synthData.synthesized_venues);
                // Only replace venues if we don't already have real venues
                if (!quickGuideData?.venues || quickGuideData.venues.length === 0) {
                  setVenues(synthData.synthesized_venues);
                }
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
      // Marco no longer auto-opens - user chooses when to chat
    }
  }, [location.city, location.neighborhood, location.country, category, categoryLabel, neighborhoodOptIn, fetchAPI, fetchQuickGuide, fetchNeighborhoods, fetchWeatherData]);

  // Handle neighborhood selection from picker
  const handleNeighborhoodSelect = useCallback((neighborhood) => {
    setLocation(prev => ({ ...prev, neighborhood }));
    setShowNeighborhoodPicker(false);
    
    // Continue with the pending search
    if (pendingCategory) {
      handleSearch(pendingCategory.label, location.city);
      setPendingCategory(null);
    }
  }, [pendingCategory, location.city, handleSearch]);

  // Handle skip neighborhood selection
  const handleSkipNeighborhood = useCallback(() => {
    setShowNeighborhoodPicker(false);
    
    // Continue with the pending search without neighborhood
    if (pendingCategory) {
      handleSearch(pendingCategory.label, location.city);
      setPendingCategory(null);
    }
  }, [pendingCategory, location.city, handleSearch]);

  // Handle category selection from CitySuggestions
  const handleCategorySelect = useCallback(async (intent, label) => {
    setCategory(intent);
    setCategoryLabel(label);
    setParsedIntent(intent);
    
    // Check if this is a large city that needs neighborhood narrowing
    if (location.city) {
      try {
        const smartData = await fetchSmartNeighborhoods(location.city, label);
        
        // Force neighborhood picker for known large cities even if fetch fails
        const largeCities = ['Guadalajara', 'Tokyo', 'Strasbourg', 'Athens', 'Rome', 'Barcelona', 'Paris', 'London', 'New York'];
        const isLargeCity = largeCities.some(city => location.city.toLowerCase().includes(city.toLowerCase())) || smartData.is_large_city;
        
        if (isLargeCity) {
          // Show neighborhood picker for large cities, using available data or empty list
          setSmartNeighborhoods(smartData.neighborhoods || []);
          setPendingCategory({ intent, label });
          setShowNeighborhoodPicker(true);
          return;
        }
        
        // Small city - search directly
        handleSearch(label, location.city);
      } catch (error) {
        console.error('Error in category select:', error);
        // Force showing the neighborhood picker with an empty list to prevent UI hang
        setSmartNeighborhoods([]);
        setPendingCategory({ intent, label });
        setShowNeighborhoodPicker(true);
        return;
      }
    }
    
    // Auto-scroll to hero image after category selection
    setTimeout(() => {
      const heroElement = document.querySelector('.hero-image-container');
      if (heroElement) {
        heroElement.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'start' 
        });
      }
    }, 100);
  }, [location.city, handleSearch, fetchSmartNeighborhoods]);

  // Memoized suggestion handler with toggle behavior
  const handleSuggestion = useCallback(async (id) => {
    // Toggle: deselect if already selected
    if (selectedSuggestion === id) {
      setCategory('');
      setCategoryLabel('');
      setSelectedSuggestion('');
      clearMarcoOpenTimer();
      // trigger a broad search with no specific category
      if (location.city) await handleSearch('');
      return;
    }

    const label = SUGGESTION_MAP[id] || id; // human label
    setCategory(id); // keep internal id
    setSelectedSuggestion(id);
    
    // Check if this is a large city that needs neighborhood narrowing
    if (location.city) {
      try {
        const smartData = await fetchSmartNeighborhoods(location.city, label);
        
        // Force neighborhood picker for known large cities even if fetch fails
        const largeCities = ['Guadalajara', 'Tokyo', 'Strasbourg', 'Athens', 'Rome', 'Barcelona', 'Paris', 'London', 'New York'];
        const isLargeCity = largeCities.some(city => location.city.toLowerCase().includes(city.toLowerCase())) || smartData.is_large_city;
        
        if (isLargeCity) {
          // Show neighborhood picker for large cities, using available data or empty list
          setSmartNeighborhoods(smartData.neighborhoods || []);
          setPendingCategory({ intent: id, label });
          setShowNeighborhoodPicker(true);
          return;
        }
        
        // Small city - search directly
        await handleSearch(label);
      } catch (error) {
        console.error('Error in suggestion select:', error);
        // Force showing the neighborhood picker with an empty list to prevent UI hang
        setSmartNeighborhoods([]);
        setPendingCategory({ intent: id, label });
        setShowNeighborhoodPicker(true);
        return;
      }
    }
  }, [location.city, handleSearch, selectedSuggestion, clearMarcoOpenTimer, fetchSmartNeighborhoods]);

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
      
      {location.city && (
        <div style={{ minWidth: 220, margin: '0 auto', maxWidth: 600 }}>
          <WeatherDisplay {...weatherDisplayProps} />
          {weatherError && (
            <div style={{ marginTop: 8, color: '#9b2c2c', fontSize: 13 }}>
              {weatherError}
            </div>
          )}
        </div>
      )}

      <div className="app-container">
        <SimpleLocationSelector 
          onLocationChange={handleSimpleLocationChange}
          onCityGuide={(city) => handleSearch(categoryLabel || category || '', city)}
        />

        {/* City Suggestions - Controlled Context */}
        {showCitySuggestions && location.city && (
          <CitySuggestions 
            city={location.city}
            onCategorySelect={handleCategorySelect}
          />
        )}

        {/* Smart Neighborhood Picker for Large Cities */}
        {showNeighborhoodPicker && (
          <NeighborhoodPicker
            city={location.city}
            category={pendingCategory?.label || categoryLabel}
            neighborhoods={smartNeighborhoods}
            onSelect={handleNeighborhoodSelect}
            onSkip={handleSkipNeighborhood}
          />
        )}

        {/* Hero Image - Visual Payoff */}
        {(location.city || cityGuideLoading) && (
          <HeroImage 
            city={location.cityName}
            intent={parsedIntent || selectedSuggestion}
            loading={cityGuideLoading}
            heroImage={heroImage}
            heroImageMeta={heroImageMeta}
          />
        )}

        {/* Fun Fact - Display below hero image */}
        {location.city && !category && !selectedSuggestion && (
          <FunFact city={location.city} />
        )}

        {/* City Guide with Fun Facts - Display below hero image */}
        {location.city && results && !category && !selectedSuggestion && (
          <SearchResults 
            results={results} 
          />
        )}

        {location.city && cityGuideLoading && (
          <div className="quick-guide quick-guide--loading" aria-live="polite" aria-busy="true">
            <div className="loading-pill" />
            <div className="loading-title loading-pulse" />
            <div className="loading-line loading-pulse" />
            <div className="loading-line loading-pulse" style={{ maxWidth: '85%' }} />
            <div className="loading-footnote">Gathering highlights for {location.city}…</div>
          </div>
        )}

        {location.city && location.neighborhood && generating && (
          <div style={{ margin: '8px 0 12px 0', color: '#3b556f' }}>
            Generating quick guide…
          </div>
        )}

        {/* Category Loading State */}
        {loading && (category || selectedSuggestion) && (
          <div style={{ 
            marginTop: 32, 
            padding: '40px 16px',
            textAlign: 'center',
            animation: 'fadeIn 0.3s ease-out'
          }}>
            <div style={{
              width: 48,
              height: 48,
              border: '4px solid #f3f3f3',
              borderTop: '4px solid #667eea',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
              margin: '0 auto 16px'
            }} />
            <p style={{ color: '#666', fontSize: 16, margin: 0 }}>
              {loadingMessage || `Finding ${categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category} in ${location.city}...`}
            </p>
          </div>
        )}
        
        {/* Empty state - category selected but no venues */}
        {(category || selectedSuggestion) && !loading && venues.length === 0 && location.city && (
          <div style={{ 
            marginTop: 32, 
            padding: '40px 16px',
            textAlign: 'center',
            background: 'linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%)',
            borderRadius: 16,
            margin: '32px 16px 0'
          }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
            <h3 style={{ color: '#333', marginBottom: 8 }}>
              Finding the best {categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category?.toLowerCase()} in {location.city}
            </h3>
            <p style={{ color: '#666', marginBottom: 16 }}>
              We're searching for top-rated spots. This may take a moment for lesser-known cities.
            </p>
            <button
              onClick={() => setMarcoOpen(true)}
              style={{
                padding: '12px 24px',
                background: '#667eea',
                color: 'white',
                border: 'none',
                borderRadius: 8,
                cursor: 'pointer',
                fontSize: '16px',
                fontWeight: 'bold'
              }}
            >
              💬 Ask Marco for personalized tips
            </button>
          </div>
        )}
        
        {/* Category Results - Show venues when category selected */}
        {(category || selectedSuggestion) && venues.length > 0 && !loading && (
          <div className="category-results" style={{ 
            marginTop: 32, 
            padding: '0 16px',
            animation: 'fadeInUp 0.5s ease-out'
          }}>
            {/* Dynamic city-specific blurb */}
            <div style={{
              background: 'linear-gradient(135deg, #2196f3 0%, #1976d2 100%)',
              borderRadius: 16,
              padding: '24px',
              marginBottom: 24,
              color: 'white',
              boxShadow: '0 8px 32px rgba(33, 150, 243, 0.3)'
            }}>
              <h3 style={{ 
                fontSize: 24, 
                marginBottom: 12, 
                color: 'white',
                fontWeight: 700
              }}>
                {categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category} in {location.city}
              </h3>
              <p style={{ 
                color: 'rgba(255,255,255,0.9)', 
                fontSize: 16, 
                lineHeight: 1.6,
                margin: 0
              }}>
                {(categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category)?.toLowerCase() === 'nightlife' 
                  ? `${location.city} comes alive after dark. From hidden speakeasies to rooftop bars with skyline views, discover where locals actually spend their evenings. Whether you're after craft cocktails, live music, or dancing until dawn, these spots capture the city's true evening energy.`
                  : (categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category)?.toLowerCase().includes('food') || (categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category)?.toLowerCase().includes('dining')
                  ? `${location.city}'s food scene tells the story of its people. From neighborhood institutions to innovative newcomers, these are the places that make locals wait in line and visitors extend their trips.`
                  : `Discover the best ${(categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category)?.toLowerCase()} spots ${location.neighborhood ? `in ${location.neighborhood}` : `across ${location.city}`}. Hand-picked venues that capture what makes this city special.`}
              </p>
            </div>
            
            <div className="venues-grid" style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', 
              gap: 20,
              marginTop: 24
            }}>
              {venues.slice(0, 6).map((venue, index) => (
                <div key={venue.id || index} className="venue-card" style={{
                  background: 'white',
                  borderRadius: 12,
                  padding: 20,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                  border: '1px solid #e8e8e8',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12
                }}>
                  {venue.image_url && (
                    <img 
                      src={venue.image_url} 
                      alt={venue.name}
                      style={{
                        width: '100%',
                        height: 180,
                        objectFit: 'cover',
                        borderRadius: 8,
                        marginBottom: 4
                      }}
                    />
                  )}
                  
                  {/* Venue Name */}
                  <h4 style={{ margin: 0, fontSize: 18, color: '#1a1a1a', fontWeight: 600 }}>
                    {venue.name}
                  </h4>
                  
                  {/* Address with Google Maps link */}
                  {(venue.address || venue.latitude || venue.lat) && (
                    <a 
                      href={(() => {
                        const lat = venue.latitude || venue.lat;
                        const lon = venue.longitude || venue.lon;
                        // Check if address is real or just coordinates placeholder
                        const hasRealAddress = venue.address && 
                          !venue.address.includes('Approximate location') && 
                          !venue.address.match(/^-?\d+\.\d+,\s*-?\d+\.\d+$/);
                        
                        if (hasRealAddress) {
                          // Use venue name + real address for search
                          return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}+${encodeURIComponent(venue.address)}`;
                        } else if (lat && lon) {
                          // Use coordinates directly - shows exact location
                          return `https://www.google.com/maps/?q=${lat},${lon}`;
                        } else {
                          return '#';
                        }
                      })()}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: '#667eea',
                        fontSize: 14,
                        textDecoration: 'none',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6
                      }}
                    >
                      📍 {(() => {
                        const hasRealAddress = venue.address && 
                          !venue.address.includes('Approximate location') && 
                          !venue.address.match(/^-?\d+\.\d+,\s*-?\d+\.\d+$/);
                        if (hasRealAddress) {
                          return venue.address;
                        }
                        const lat = venue.latitude || venue.lat;
                        const lon = venue.longitude || venue.lon;
                        if (lat && lon) {
                          return `${parseFloat(lat).toFixed(4)}, ${parseFloat(lon).toFixed(4)}`;
                        }
                        return location.city;
                      })()}
                    </a>
                  )}
                  
                  {/* Description */}
                  {venue.description && (
                    <p style={{ 
                      margin: 0, 
                      fontSize: 14, 
                      color: '#555', 
                      lineHeight: 1.5 
                    }}>
                      {venue.description}
                    </p>
                  )}
                  
                  {/* Opening Hours */}
                  {(venue.opening_hours || venue.opening_hours_pretty) && (
                    <div style={{ fontSize: 13, color: '#666' }}>
                      🕒 {venue.opening_hours_pretty || venue.opening_hours}
                    </div>
                  )}
                  
                  {/* Tags */}
                  {venue.tags && typeof venue.tags === 'object' && !Array.isArray(venue.tags) && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {Object.entries(venue.tags).slice(0, 3).map(([key, value]) => (
                        <span key={key} style={{
                          fontSize: 11,
                          padding: '4px 8px',
                          background: '#f0f4f8',
                          borderRadius: 12,
                          color: '#667eea'
                        }}>
                          {typeof value === 'string' ? value.replace(/_/g, ' ') : key}
                        </span>
                      ))}
                    </div>
                  )}
                  
                  {/* Action Buttons */}
                  <div style={{ 
                    display: 'flex', 
                    gap: 10, 
                    marginTop: 'auto',
                    paddingTop: 12,
                    borderTop: '1px solid #eee'
                  }}>
                    {(venue.latitude || venue.lat) && (
                      <a
                        href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(venue.name)},${venue.latitude || venue.lat},${venue.longitude || venue.lon}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          flex: 1,
                          padding: '10px 16px',
                          background: '#667eea',
                          color: 'white',
                          borderRadius: 8,
                          textDecoration: 'none',
                          fontSize: 13,
                          fontWeight: 600,
                          textAlign: 'center'
                        }}
                      >
                        Get Directions
                      </a>
                    )}
                    <button
                      onClick={() => {
                        setMarcoOpen(true);
                        // Store the venue question to be used when Marco opens
                        localStorage.setItem('marco_initial_question', `Tell me more about ${venue.name}${venue.description ? ' - ' + venue.description : ''}. What makes it special?`);
                      }}
                      style={{
                        flex: 1,
                        padding: '10px 16px',
                        background: '#9c27b0',
                        color: 'white',
                        borderRadius: 8,
                        border: 'none',
                        fontSize: 13,
                        fontWeight: 600,
                        textAlign: 'center',
                        cursor: 'pointer'
                      }}
                    >
                      🤖 Ask Marco
                    </button>
                    {venue.website && (
                      <a
                        href={venue.website}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          flex: 1,
                          padding: '10px 16px',
                          background: '#f0f4f8',
                          color: '#667eea',
                          borderRadius: 8,
                          textDecoration: 'none',
                          fontSize: 13,
                          fontWeight: 600,
                          textAlign: 'center'
                        }}
                      >
                        Website
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {location.city && (
        <div style={{ display: 'flex', gap: 12, marginTop: 24, flexWrap: 'wrap', padding: '0 16px' }}>
          <button
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
            💬 Ask Marco for personalized tips
          </button>
        </div>
      )}

        {marcoOpen && (
          <MarcoChat
            city={location.city}
            neighborhood={location.neighborhood}
            venues={venues}
            category={categoryLabel || SUGGESTION_MAP[selectedSuggestion] || (typeof category === 'string' ? category : '')}
            initialInput=""
            results={results}
            wikivoyage={results?.wikivoyage}
            onClose={() => setMarcoOpen(false)}
          />
        )}
      </div>
    </div>
  );
}

export default App;
