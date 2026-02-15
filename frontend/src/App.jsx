import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import CitySuggestions from './components/CitySuggestions';
import FunFact from './components/FunFact';
import Header from './components/Header';
import HeroImage from './components/HeroImage';
import MarcoChat from './components/MarcoChat';
import NeighborhoodGuide from './components/NeighborhoodGuide';
import NeighborhoodPicker from './components/NeighborhoodPicker';
import SearchResults from './components/SearchResults';
import SimpleLocationSelector from './components/SimpleLocationSelector';
import WeatherDisplay from './components/WeatherDisplay';
import { getHeroImage, getHeroImageMeta } from './services/imageService';

// Constants moved outside component to avoid recreation
const CITY_LIST = ['Rio de Janeiro', 'London', 'New York', 'Lisbon'];
const COUNTRIES = ['USA', 'Mexico', 'Spain', 'UK', 'France', 'Germany', 'Italy', 'Canada', 'Australia', 'Japan', 'China', 'India', 'Brazil', 'Argentina', 'South Africa', 'Netherlands', 'Portugal', 'Sweden', 'Norway', 'Denmark', 'Iceland'];

// Reduced popular cities list
const POPULAR_CITIES = [
  'New York', 'London', 'Paris', 'Tokyo', 'Sydney', 'Rio de Janeiro', 'Lisbon', 'Reykjavik', 'Berlin', 'Rome', 'Barcelona', 'Amsterdam', 'Vienna', 'Prague', 'Budapest'
];

// Hidden gem inspirations (fetching dynamic images, no static assets)
  const HIDDEN_GEM_CITIES = [
    'Bucharest, Romania',
    'Mostar Bosnia',
    'Kotor Montenegro',
    'Oaxaca Mexico',
    'Puglia Italy',
    'Chefchaouen Morocco',
    'Svalbard Norway',
    'Isle of Skye Scotland'
  ];

const FEATURE_PALETTE = [
  ['#1db6e0', '#0f172a'],
  ['#e8751a', '#0f172a'],
  ['#7c3aed', '#1db6e0'],
  ['#10b981', '#0f172a'],
  ['#f59e0b', '#1e293b'],
];

const gradientForName = (label = '') => {
  const idx = Math.abs(label.split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0)) % FEATURE_PALETTE.length;
  return FEATURE_PALETTE[idx];
};

// (Removed hard-coded neighborhood fallbacks – data now comes exclusively from backend seed JSON)

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
  const [selectedSuggestion, setSelectedSuggestion] = useState('hidden');
  const [marcoOpen, setMarcoOpen] = useState(false);
  const [marcoWebRAG, setMarcoWebRAG] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [cityGuideLoading, setCityGuideLoading] = useState(false);
  const [parsedIntent, setParsedIntent] = useState('');
  const [venues, setVenues] = useState([]);
  const [heroImage, setHeroImage] = useState('');
  const [heroImageMeta, setHeroImageMeta] = useState({});
  const [showCitySuggestions, setShowCitySuggestions] = useState(true);
  const [showNeighborhoodPicker, setShowNeighborhoodPicker] = useState(false);
  const [showNeighborhoodGuide, setShowNeighborhoodGuide] = useState(false);
  const [neighborhoodGuideData, setNeighborhoodGuideData] = useState(null);
  const [neighborhoodGuideLoading, setNeighborhoodGuideLoading] = useState(false);
  const [neighborhoodGuideError, setNeighborhoodGuideError] = useState(null);
  const [smartNeighborhoods, setSmartNeighborhoods] = useState([]);
  const [pendingCategory, setPendingCategory] = useState(null);
  const [neighborhoodsLoading, setNeighborhoodsLoading] = useState(false);
  const [featuredImages, setFeaturedImages] = useState({});
  const [showPopular, setShowPopular] = useState(false);
  const [activePanel, setActivePanel] = useState('categories');
  const [isDesktop, setIsDesktop] = useState(false);
  const marcoOpenTimerRef = useRef(null);
  const citySuggestionsRef = useRef(null);
  const cityGuideRef = useRef(null);

  const scrollToCitySuggestions = useCallback(() => {
    const el = cityGuideRef.current || citySuggestionsRef.current;
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)');
    const handler = (e) => setIsDesktop(e.matches);
    handler(mq);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

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

  const fetchWeatherData = useCallback(async (city, neighborhood = '') => {
    if (!city) {
      setWeather(null);
      return;
    }

    setWeatherError(null);

    try {
      const geo = await fetchAPI('/api/geocode', {
        method: 'POST',
        body: JSON.stringify({ city, neighborhood })
      });

      const lat = geo?.lat ?? geo?.latitude;
      const lon = geo?.lon ?? geo?.longitude ?? geo?.lng;
      if (!lat || !lon) {
        setWeather(null);
        return;
      }

      const data = await fetchAPI('/api/weather', {
        method: 'POST',
        body: JSON.stringify({ city, lat, lon })
      });

      if (data?.weather) {
        setWeather(data.weather);
      } else {
        setWeather(null);
      }
    } catch (err) {
      console.error('Failed to fetch weather', err);
      setWeatherError('Unable to load weather right now.');
      setWeather(null);
    }
  }, [fetchAPI]);

  // Prefetch imagery + credit for hidden-gem featured cities
  useEffect(() => {
    let cancelled = false;
    const loadDefaultImages = async () => {
      const targets = HIDDEN_GEM_CITIES.filter((city) => !featuredImages[city]);
      if (targets.length === 0) return;
      const promises = targets.map(async (city) => {
        try {
          const meta = await getHeroImageMeta(city, 'hidden gems');
          return { city, img: meta?.url || '', credit: meta?.photographer, profile: meta?.profileUrl };
        } catch (e) {
          return { city, img: '', credit: '', profile: '' };
        }
      });
      const results = await Promise.all(promises);
      if (cancelled) return;
      setFeaturedImages((prev) => {
        const next = { ...prev };
        results.forEach(({ city, img, credit, profile }) => { next[city] = { img, credit, profile }; });
        return next;
      });
    };
    loadDefaultImages();
    return () => { cancelled = true; };
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

      // Auto-scroll to guide stack after city selection
      setTimeout(() => {
        scrollToCitySuggestions();
      }, 100);
    }

    // Reset category selections when city changes
    setCategory('');
    setCategoryLabel('');
    setSelectedSuggestion('');

    // Reset results to trigger fresh city guide fetch
    setResults(null);

    // Enable neighborhood opt-in for the new city
    setNeighborhoodOptIn(true);

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
        const data = await fetchAPI(`/api/neighborhoods?city=${encodeURIComponent(cityName)}&lang=en`);
        if (data?.neighborhoods?.length > 0) {
          cityData = data.neighborhoods.map(n => n.name || n.display_name || n.label || n.id).filter(Boolean);
        }
      } catch {}
      try {
        const data = await fetchAPI(`/api/neighborhoods?lat=${lat}&lon=${lon}&lang=en`);
        if (data?.neighborhoods?.length > 0) {
          coordData = data.neighborhoods.map(n => n.name || n.display_name || n.label || n.id).filter(Boolean);
        }
      } catch {}
      const fallbackNames = [];
      // Merge and deduplicate
      return Array.from(new Set([...cityData, ...coordData]));
    }

    try {
      // First try fetching by city name
      const data = await fetchAPI(`/api/neighborhoods?city=${encodeURIComponent(cityName)}&lang=en`);
      if (data?.neighborhoods?.length > 0) {
        const names = data.neighborhoods.map(n => n.name || n.display_name || n.label || n.id).filter(Boolean);
        const uniqueNames = Array.from(new Set(names));
        const fallbackNames = [];
        return uniqueNames;
      }
      // If city-based fetch failed or returned no results, try geocoding to get coordinates
      try {
        const geoData = await fetchAPI('/api/geocode', {
          method: 'POST',
          body: JSON.stringify({ city: cityName })
        });
        const lat = geoData?.lat ?? geoData?.latitude;
        const lon = geoData?.lon ?? geoData?.longitude ?? geoData?.lng;
        if (lat && lon) {
          // Try fetching by coordinates
          const coordData = await fetchAPI(`/api/neighborhoods?lat=${lat}&lon=${lon}&lang=en`);
          if (coordData?.neighborhoods?.length > 0) {
            const names = coordData.neighborhoods.map(n => n.name || n.display_name || n.label || n.id).filter(Boolean);
            const uniqueNames = Array.from(new Set(names));
            const fallbackNames = [];
            return uniqueNames;
          }
        }
      } catch (geoErr) {
        // Continue to fallback
      }
    } catch (err) {
      // Continue to fallback
    }
    return [];
  }, [fetchAPI]);

  // Fetch smart neighborhood suggestions for large cities with a timeout
  const fetchSmartNeighborhoods = useCallback(async (city, category = '') => {
    if (!city) return { is_large_city: false, neighborhoods: [] };

    setNeighborhoodsLoading(true);

    try {
      const attempt = async (label) => {
        const started = performance.now();
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 25000);
        try {
          const resp = await fetch(`${API_BASE}/api/smart-neighborhoods?city=${encodeURIComponent(city)}&category=${encodeURIComponent(category)}`, { signal: controller.signal });
          const elapsed = Math.round(performance.now() - started);
          console.log('[SMART-NHOOD]', label, 'ms=', elapsed, 'status=', resp.status);
          if (!resp.ok) {
            return null;
          }
          return await resp.json();
        } catch (err) {
          console.warn('[SMART-NHOOD]', label, 'error:', err?.message || err);
          return null;
        } finally {
          clearTimeout(timeoutId);
        }
      };

      const first = await attempt('primary');
      if (first && first.neighborhoods) return first;
      const retry = await attempt('retry');
      if (retry && retry.neighborhoods) return retry;

      return { is_large_city: true, neighborhoods: [] };
    } catch (error) {
      console.error('Failed to fetch smart neighborhoods:', error.message, error.stack);
      // Fallback to any cached neighborhoods or empty list with large city flag to show picker if possible
      return { is_large_city: true, neighborhoods: [] };
    } finally {
      setNeighborhoodsLoading(false);
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
      return await fetchAPI('/api/search', {
        method: 'POST',
        body: JSON.stringify(searchParams)
      });
    } catch (error) {
      return null;
    }
  }, [fetchAPI]);

  // Fetch neighborhood guide
  const fetchNeighborhoodGuide = useCallback(async (city, neighborhood, country = '') => {
    if (!city || !neighborhood) return;
    
    setNeighborhoodGuideLoading(true);
    setNeighborhoodGuideData(null);
    setNeighborhoodGuideError(null);
    setShowNeighborhoodGuide(true);
    
    try {
      const data = await fetchAPI('/api/generate_quick_guide', {
        method: 'POST',
        body: JSON.stringify({ city, neighborhood, country })
      });
      
      if (data) {
        setNeighborhoodGuideData(data);
        
        // Also update main results so the background reflects the neighborhood guide
        if (data.quick_guide) {
          setResults(prev => ({
            ...prev,
            quick_guide: data.quick_guide,
            source: data.source,
            cached: data.cached,
            source_url: data.source_url,
            confidence: data.confidence,
            ...(data.mapillary_images && { mapillary_images: data.mapillary_images })
          }));
        }
      } else {
        throw new Error('No guide data received');
      }
    } catch (err) {
      console.error('Fetch neighborhood guide failed:', err);
      setNeighborhoodGuideError('Failed to load neighborhood insights.');
    } finally {
      setNeighborhoodGuideLoading(false);
    }
  }, [fetchAPI]);

  // Main search function - defined with useCallback to avoid recreation
  const handleSearch = useCallback(async (overrideCategory = null, cityOverride = null, neighborhoodOverride = null) => {
    const searchCity = cityOverride || location.city;
    if (!searchCity?.trim()) {
      setWeatherError('Please select a city before searching.');
      return;
    }

    const neighborhood = neighborhoodOverride || location.neighborhood;
    const displayCategory = overrideCategory || categoryLabel || category;
    const message = neighborhood 
      ? `Finding ${displayCategory || 'great spots'} in ${neighborhood}, ${searchCity}...`
      : `Finding ${displayCategory || 'great spots'} in ${searchCity}...`;
    
    setLoadingMessage(message);
    setLoading(true);

    try {
      // Parallel API calls for better performance
      const [geoData, quickGuideData] = await Promise.all([
        fetchAPI('/api/geocode', {
          method: 'POST',
          body: JSON.stringify({ city: searchCity, neighborhood: neighborhood || '', country: location.country })
        }).catch(() => null),
        
        fetchQuickGuide({
          query: searchCity,
          state: location.state,
          country: location.country,
          ...(neighborhood && neighborhoodOptIn && { neighborhood }),
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
          } catch (e) {
            console.warn('Neighborhood fetch failed', e);
          }
        }
      }

      // Fetch weather if we have coordinates
      if (geoData?.lat && geoData?.lon) {
        await fetchWeatherData(searchCity, neighborhood);
      }

      // Set results from quick guide
      if (!quickGuideData) {
        setResults({
          quick_guide: buildCityFallback(searchCity),
          source: 'fallback',
          cached: false,
          categories: ['food', 'nightlife', 'culture', 'shopping', 'parks', 'historic sites', 'beaches', 'markets']
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
        } else {
          setVenues([]);
        }

        // Start synthesis in background only when we have real guide text
        if (quickGuideData.quick_guide && !looksLikeMisalignedGuide(quickGuideData.quick_guide, location.city) || quickGuideData.summary) {
          setSynthLoading(true);
          fetchAPI('/api/synthesize', {
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
    }
  }, [location.city, location.neighborhood, location.country, category, categoryLabel, neighborhoodOptIn, fetchAPI, fetchQuickGuide, fetchNeighborhoods, fetchWeatherData, buildCityFallback]);

  // Initial search effect to fetch categories and quick guide on city selection
  useEffect(() => {
    if (location.city && !results) {
      handleSearch('', location.city);
    }
  }, [location.city, handleSearch, results]);

  const handleCategorySelect = useCallback(async (opt) => {
    const value = (opt && (opt.value || opt.id || opt.key)) || opt || '';
    const label = (opt && (opt.label || opt.name)) || value;
    setPendingCategory(opt || null);
    setCategory(value);
    setCategoryLabel(label);
    setActivePanel('neighborhoods');

    await handleSearch(value);
  }, [handleSearch]);

  const handleNeighborhoodSelect = useCallback(async (neighborhood) => {
    setLocation(prev => ({ ...prev, neighborhood }));
    await fetchNeighborhoodGuide(location.city, neighborhood, location.country);
  }, [location.city, location.country, fetchNeighborhoodGuide]);

  const handleSkipNeighborhood = useCallback(async () => {
    setLocation(prev => ({ ...prev, neighborhood: '' }));
    await handleSearch(categoryLabel || category);
  }, [categoryLabel, category, handleSearch]);

  const handleNeighborhoodGuideClose = useCallback(() => {
    setShowNeighborhoodGuide(false);
    setNeighborhoodGuideData(null);
    setNeighborhoodGuideError(null);
    
    if (location.neighborhood) {
      handleSearch(categoryLabel || category, location.city, location.neighborhood);
    }
    
    scheduleMarcoOpen();
  }, [location.city, location.neighborhood, categoryLabel, category, handleSearch, scheduleMarcoOpen]);

  // Memoized component values
  const weatherDisplayProps = useMemo(() => ({
    weather,
    city: location.city
  }), [weather, location.city]);

  return (
    <div className="min-h-screen text-slate-900">
      <Header 
        city={location.city} 
        neighborhood={location.neighborhood}
        weather={weather}
        weatherError={weatherError}
      />

      {/* Hero / welcome */}
      <section
        className="relative max-w-6xl mx-auto mt-6 px-4"
      >
        <div
          className="relative overflow-visible rounded-3xl bg-gradient-to-r from-brand-orange/90 via-brand-orange to-brand-aqua/80 text-white shadow-2xl min-h-[360px] lg:min-h-[420px]"
          style={heroImage ? {
            backgroundImage: `linear-gradient(90deg, rgba(59,130,246,0.9), rgba(59,130,246,0.6)), url(${heroImage})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center'
          } : {}}
        >
          <div className="absolute inset-0 backdrop-blur-sm" style={heroImage ? { background: 'linear-gradient(90deg, rgba(232,117,26,0.82), rgba(29,182,224,0.68))' } : {}} />
          <div className="relative grid gap-8 lg:grid-cols-[1.2fr,0.8fr] p-6 lg:p-10 max-w-5xl mx-auto">
            <div className="space-y-3">
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold leading-tight">Discover your next adventure</h1>
              <p className="text-white/90 text-base sm:text-lg">Pick a city to unlock categories, neighborhoods, guides, and Marco chat.</p>
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl shadow-xl p-4 sm:p-5 text-slate-100 backdrop-blur">
                <SimpleLocationSelector 
                  onLocationChange={handleSimpleLocationChange}
                  onCityGuide={(city) => handleSearch(categoryLabel || category || '', city)}
                />
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm text-white/90">
                <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10">🌍 Popular cities</span>
                <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10">⚡ Categories & neighborhoods</span>
                <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10">💬 Marco chat</span>
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start" />
          </div>
        </div>
      </section>

      <div className="max-w-6xl mx-auto px-4 pb-16 space-y-10">

        {/* Popular (toggle) + Featured */}
        <div className="mt-10 space-y-5">
          <div className="rounded-2xl bg-white/90 border border-slate-200 shadow-lg backdrop-blur p-4 text-slate-900">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-700 font-semibold"><span>🌐</span> Popular destinations</div>
              <button
                className="text-sm text-brand-orange font-semibold hover:underline"
                onClick={() => setShowPopular(!showPopular)}
              >
                {showPopular ? 'Hide' : 'Browse'}
              </button>
            </div>
            {showPopular && (
              <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {POPULAR_CITIES.map(city => (
                  <button
                    key={city}
                    onClick={() => handleSimpleLocationChange({ city, cityName: city })}
                    className="rounded-xl bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-800 shadow hover:shadow-md hover:bg-brand-orange/10 transition"
                  >
                    {city}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-2xl bg-gradient-to-br from-brand-orange/90 via-brand-orange to-brand-aqua/80 text-white shadow-lg p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xl font-semibold">Featured vibes</h2>
              <span className="text-sm text-white/80">Swipe</span>
            </div>
            <div className="flex gap-6 overflow-x-auto pb-4 snap-x snap-mandatory">
              {((category || (selectedSuggestion && venues.length > 0))
                ? venues.slice(0, 6).map((v, idx) => ({ key: v.id || idx, name: v.name, description: v.description || 'Obscure local gem with atmosphere.' }))
                : HIDDEN_GEM_CITIES.map((city) => ({ key: city, name: city, description: `Hidden corners of ${city}`, img: featuredImages[city]?.img || '', credit: featuredImages[city]?.credit, profile: featuredImages[city]?.profile })))
                .map((item) => {
                  const [from, to] = gradientForName(item.name);
                  const card = (
                    <div
                      className="min-w-[340px] min-h-[280px] snap-start rounded-2xl p-6 shadow-2xl text-left text-white border border-white/10 overflow-hidden"
                      style={{ backgroundImage: item.img ? `linear-gradient(135deg, rgba(0,0,0,0.35), rgba(0,0,0,0.6)), url(${item.img})` : `linear-gradient(135deg, ${from}, ${to})`, backgroundSize: 'cover', backgroundPosition: 'center' }}
                    >
                      <p className="text-2xl font-semibold leading-tight drop-shadow-sm">{item.name}</p>
                      {item.credit && (
                        <p className="mt-3 text-[12px] text-white/85">Photo: <a className="underline" href={item.profile || '#'} target="_blank" rel="noreferrer">{item.credit}</a></p>
                      )}
                    </div>
                  );
                  return (
                    <button
                      key={item.key}
                      type="button"
                      className="text-left w-full max-w-[340px]"
                      onClick={() => {
                        handleSimpleLocationChange({ city: item.name, cityName: item.name });
                        scrollToCitySuggestions();
                      }}
                    >
                      {card}
                    </button>
                  );
                })}
            </div>
          </div>
        </div>

        <div ref={cityGuideRef}>
          {weather && (
            <div className="mt-6 rounded-2xl border border-white/20 bg-gradient-to-br from-brand-ink/85 via-brand-orange/85 to-brand-aqua/80 text-white shadow-2xl p-5 backdrop-blur">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">🌤️</span>
                  <div className="text-sm font-semibold">{location.city}</div>
                </div>
                <span className="text-xs uppercase tracking-wide text-white/80">Weather</span>
              </div>
              <div className="mt-3">
                <WeatherDisplay {...weatherDisplayProps} />
              </div>
            </div>
          )}

          {/* Mobile panel toggles */}
          {location.city && (
            <div className="mt-6 flex flex-wrap gap-2 md:hidden">
              {[
                { key: 'categories', label: 'Categories' },
                { key: 'neighborhoods', label: 'Nearby Attractions' },
                { key: 'guide', label: 'Guide' },
                { key: 'fun', label: 'Fun Fact' },
              ].map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActivePanel(tab.key)}
                  className={`px-3 py-2 rounded-full text-sm font-semibold border transition ${activePanel === tab.key ? 'bg-brand-orange text-white border-brand-orange' : 'bg-white border-slate-200 text-slate-800'}`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          {/* City Suggestions - Controlled Context */}
          {showCitySuggestions && location.city && (
            <div className={`mt-6 ${activePanel === 'categories' || isDesktop ? '' : 'hidden md:block'}`} ref={citySuggestionsRef}>
              <CitySuggestions 
                city={location.city}
                onCategorySelect={handleCategorySelect}
                searchResults={results}
              />
            </div>
          )}

          {/* Inline neighborhoods pane to keep unified experience */}
          {(smartNeighborhoods.length > 0 || neighborhoodsLoading) && (
            <div className={`mt-6 rounded-2xl border border-slate-200 bg-white shadow-lg p-4 text-slate-900 ${activePanel === 'neighborhoods' || isDesktop ? '' : 'hidden md:block'}`}>
              <NeighborhoodPicker
                inline
                city={location.city}
                category={pendingCategory?.label || categoryLabel}
                neighborhoods={smartNeighborhoods}
                onSelect={handleNeighborhoodSelect}
                onSkip={handleSkipNeighborhood}
                loading={neighborhoodsLoading}
              />
            </div>
          )}

          {/* Hero Image - Visual Payoff */}
          {(location.city || cityGuideLoading) && (
            <div className={`${activePanel === 'guide' || isDesktop ? '' : 'hidden md:block'}`}>
              <HeroImage 
                city={location.cityName}
                intent={parsedIntent || selectedSuggestion}
                loading={cityGuideLoading}
                heroImage={heroImage}
                heroImageMeta={heroImageMeta}
              />
            </div>
          )}

          {/* Fun Fact - Display below hero image */}
          {location.city && !category && !selectedSuggestion && (
            <div className={`mt-6 rounded-2xl border border-slate-200 bg-white shadow-lg p-4 text-slate-900 ${activePanel === 'fun' || isDesktop ? '' : 'hidden md:block'}`}>
              <FunFact city={location.city} />
            </div>
          )}

          {/* City Guide with Fun Facts - Display below hero image */}
          {location.city && results && !category && !selectedSuggestion && (
            <div className={`mt-6 rounded-2xl border border-slate-200 bg-white shadow-lg p-4 text-slate-900 ${activePanel === 'guide' || isDesktop ? '' : 'hidden md:block'}`}>
              <SearchResults 
                results={results} 
              />
            </div>
          )}
        </div>

        {location.city && cityGuideLoading && (
          <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-lg" aria-live="polite" aria-busy="true">
            <div className="h-3 w-24 rounded-full bg-gradient-to-r from-brand-orange/70 via-brand-orange/40 to-brand-aqua/70 animate-pulse" />
            <div className="mt-3 h-5 w-48 rounded-full bg-slate-200 animate-pulse" />
            <div className="mt-3 h-4 w-full rounded-full bg-slate-200 animate-pulse" />
            <div className="mt-2 h-4 w-5/6 rounded-full bg-slate-200 animate-pulse" />
            <div className="mt-4 text-sm text-slate-600">Gathering highlights for {location.city}…</div>
          </div>
        )}


        {/* Category Results - Show venues when category selected or Nearby Attractions active */}
        {(activePanel === 'neighborhoods' || category || selectedSuggestion) && venues.length > 0 && !loading && (
          <div className="mt-12 space-y-6">
            {/* Dynamic city-specific blurb */}
            <div className="rounded-2xl bg-gradient-to-r from-brand-orange via-brand-orange to-brand-aqua text-white p-6 shadow-xl">
              <h3 className="text-2xl font-bold mb-2">
                {categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category} in {location.city}
              </h3>
              <p className="text-white/90 text-base md:text-lg leading-relaxed">
                {(categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category)?.toLowerCase() === 'nightlife' 
                  ? `${location.city} comes alive after dark. From hidden speakeasies to rooftop bars with skyline views, discover where locals actually spend their evenings. Whether you're after craft cocktails, live music, or dancing until dawn, these spots capture the city's true evening energy.`
                  : (categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category)?.toLowerCase().includes('food') || (categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category)?.toLowerCase().includes('dining')
                  ? `${location.city}'s food scene tells the story of its people. From neighborhood institutions to innovative newcomers, these are the places that make locals wait in line and visitors extend their trips.`
                  : `Discover the best ${(categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category)?.toLowerCase()} spots ${location.neighborhood ? `in ${location.neighborhood}` : `across ${location.city}`}. Hand-picked venues that capture what makes this city special.`}
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              {venues.slice(0, 6).map((venue, index) => (
                <div key={venue.id || index} className="bg-white border border-slate-100 rounded-xl shadow-sm overflow-hidden flex flex-col">
                  {venue.image_url && (
                    <img 
                      src={venue.image_url} 
                      alt={venue.name}
                      className="w-full h-48 object-cover"
                    />
                  )}

                  <div className="p-4 flex flex-col gap-3">
                    {/* Venue Name */}
                    <h4 className="text-lg font-semibold text-slate-900">{venue.name}</h4>

                    {/* Address with Google Maps link */}
                    {(venue.address || venue.latitude || venue.lat) && (
                      <a 
                        href={(() => {
                          const lat = venue.latitude || venue.lat;
                          const lon = venue.longitude || venue.lon;
                          const hasRealAddress = venue.address && 
                            !venue.address.includes('Approximate location') && 
                            !venue.address.match(/^-?\d+\.\d+,\s*-?\d+\.\d+$/);
                          if (hasRealAddress) {
                            return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}+${encodeURIComponent(venue.address)}`;
                          } else if (lat && lon) {
                            return `https://www.google.com/maps/?q=${lat},${lon}`;
                          }
                          return '#';
                        })()}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand-aqua text-sm font-medium inline-flex items-center gap-2"
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

                    <details className="group rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-2 text-sm text-slate-700">
                      <summary className="cursor-pointer select-none font-semibold text-slate-800 flex items-center justify-between">
                        Details
                        <span className="text-xs text-brand-aqua group-open:hidden">Show</span>
                        <span className="text-xs text-brand-aqua hidden group-open:inline">Hide</span>
                      </summary>
                      <div className="mt-2 space-y-2">
                        {/* Description */}
                        {venue.description && (
                          <p className="leading-relaxed text-slate-700">{venue.description}</p>
                        )}

                        {/* Opening Hours */}
                        {(venue.opening_hours || venue.opening_hours_pretty) && (
                          <div className="text-sm text-slate-600">🕒 {venue.opening_hours_pretty || venue.opening_hours}</div>
                        )}

                        {/* Tags */}
                        {venue.tags && typeof venue.tags === 'object' && !Array.isArray(venue.tags) && (
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(venue.tags).slice(0, 3).map(([key, value]) => (
                              <span key={key} className="px-3 py-1 rounded-full bg-slate-200 text-xs font-semibold text-slate-700">
                                {typeof value === 'string' ? value.replace(/_/g, ' ') : key}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </details>

                    {/* Action Buttons */}
                    <div className="flex flex-wrap gap-2 pt-3 border-t border-slate-200">
                      {(venue.latitude || venue.lat) && (
                        <a
                          href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(venue.name)},${venue.latitude || venue.lat},${venue.longitude || venue.lon}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex-1 min-w-[140px] text-center rounded-lg bg-brand-aqua text-brand-ink px-4 py-2 text-sm font-semibold shadow-sm hover:bg-brand-aquaDark"
                        >
                          Get Directions
                        </a>
                      )}
                      <button
                        onClick={() => {
                          setMarcoOpen(true);
                          localStorage.setItem('marco_initial_question', `Tell me more about ${venue.name}${venue.description ? ' - ' + venue.description : ''}. What makes it special?`);
                        }}
                        className="flex-1 min-w-[140px] text-center rounded-lg bg-brand-orange text-white px-4 py-2 text-sm font-semibold shadow-sm hover:bg-brand-orangeDark"
                      >
                        🤖 Ask Marco
                      </button>
                      {venue.website && (
                        <a
                          href={venue.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex-1 min-w-[140px] text-center rounded-lg bg-slate-100 text-slate-800 px-4 py-2 text-sm font-semibold hover:bg-slate-200"
                        >
                          Website
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Floating Marco Chat button (visible after city + category) */}
        {location.city && (category || selectedSuggestion) && (
          <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
            <button
              onClick={() => setMarcoOpen(true)}
              className="rounded-full bg-brand-orange text-white shadow-xl px-5 py-3 text-sm font-semibold hover:bg-brand-orangeDark hover:scale-105 transition-transform"
            >
              💬 Ask Marco
            </button>
          </div>
        )}

        {showNeighborhoodGuide && (
          <NeighborhoodGuide
            city={location.city}
            neighborhood={location.neighborhood}
            guideData={neighborhoodGuideData}
            loading={neighborhoodGuideLoading}
            error={neighborhoodGuideError}
            onClose={handleNeighborhoodGuideClose}
          />
        )}

        {marcoOpen && (
          <MarcoChat
            city={location.city}
            neighborhood={location.neighborhood}
            venues={[]}
            category={categoryLabel || SUGGESTION_MAP[selectedSuggestion] || (typeof category === 'string' ? category : '')}
            initialInput={`Tell me about ${categoryLabel || SUGGESTION_MAP[selectedSuggestion] || category} in ${location.neighborhood ? `${location.neighborhood}, ` : ''}${location.city}`}
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
