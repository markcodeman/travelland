import React, { useState, useEffect } from 'react';
import './styles/app.css';
import AutocompleteInput from './components/AutocompleteInput';
import CategoryChips from './components/CategoryChips';
import WeatherDisplay from './components/WeatherDisplay';
import SearchResults from './components/SearchResults';
import Header from './components/Header';
import SuggestionChips from './components/SuggestionChips';
import NeighborhoodSelect from './components/NeighborhoodSelect';

// Example static city list; backend will provide neighborhoods dynamically
const cityList = [
  'Rio de Janeiro',
  'London',
  'New York',
  'Lisbon',
];
const categories = [
  'Food', 'Nightlife', 'Culture', 'Outdoors', 'Shopping', 'Family', 'History', 'Beaches'
];

function App() {
  const [city, setCity] = useState('');
  const [neighborhood, setNeighborhood] = useState('');
  const [neighborhoodOptions, setNeighborhoodOptions] = useState([]);
  const [category, setCategory] = useState('');
  const [weather, setWeather] = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch neighborhoods from backend when city changes
  useEffect(() => {
    async function fetchNeighborhoods() {
      setNeighborhoodOptions([]);
      setNeighborhood('');
      if (!city) return;
      try {
        const resp = await fetch(`http://localhost:5010/neighborhoods?city=${encodeURIComponent(city)}&lang=en`);
        const data = await resp.json();
        if (data && Array.isArray(data.neighborhoods) && data.neighborhoods.length > 0) {
          const names = data.neighborhoods.map(n => n.name || n.display_name || n.label || n.id).filter(Boolean);
          if (names.length > 0) {
            setNeighborhoodOptions(names);
            return;
          }
        }
      } catch (err) {
        // ignore fetch errors and fall back
      }
      // fallback static mapping for a few cities
      const fallback = {
        'Rio de Janeiro': ['Copacabana', 'Ipanema', 'Leblon', 'Santa Teresa', 'Barra da Tijuca', 'Lapa', 'Botafogo', 'Jardim Botânico', 'Gamboa', 'Leme', 'Vidigal'],
        'London': ['Camden', 'Chelsea', 'Greenwich', 'Soho', 'Shoreditch'],
        'New York': ['Manhattan', 'Brooklyn', 'Harlem', 'Queens', 'Bronx'],
        'Lisbon': ['Baixa', 'Chiado', 'Alfama', 'Bairro Alto', 'Belém']
      };
      setNeighborhoodOptions(fallback[city] || []);
    }
    fetchNeighborhoods();
  }, [city]);

  // Fetch a quick guide when city changes (best-effort) so the QuickGuide card is populated
  useEffect(() => {
    let mounted = true;
    async function fetchQuickGuide() {
      if (!city) return;
      try {
        const resp = await fetch('http://localhost:5010/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ city })
        });
        const data = await resp.json();
        if (!mounted) return;
        // Only set results if there's a quick_guide or summary to show
        if (data && (data.quick_guide || data.summary || data.quickGuide)) {
          setResults(data);
        }
      } catch (err) {
        // ignore errors silently
      }
    }
    fetchQuickGuide();
    return () => { mounted = false; };
  }, [city]);

  // When a neighborhood is selected, request a neighborhood-scoped quick guide
  useEffect(() => {
    let mounted = true;
    const timer = setTimeout(async () => {
      if (!city || !neighborhood) return;
      try {
        const resp = await fetch('http://localhost:5010/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ city, neighborhood, query: neighborhood })
        });
        const data = await resp.json();
        if (!mounted) return;
        if (data && (data.quick_guide || data.summary || data.quickGuide)) {
          setResults(data);
        } else {
          // no quick guide returned by /search -> automatically generate a data-first guide
          try {
            setGenerating(true);
            const gresp = await fetch('http://localhost:5010/generate_quick_guide', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ city, neighborhood })
            });
            const gdata = await gresp.json();
            if (!mounted) return;
            if (gdata && gdata.quick_guide) {
              setResults({ quick_guide: gdata.quick_guide, source: gdata.source, cached: gdata.cached, source_url: gdata.source_url });
            }
          } catch (err) {
            // ignore
          } finally {
            setGenerating(false);
          }
        }
      } catch (err) {
        // ignore errors
      }
    }, 250);
    return () => { mounted = false; clearTimeout(timer); };
  }, [city, neighborhood]);

  // Fetch weather when city changes (best-effort using backend endpoint)
  useEffect(() => {
    async function fetchWeather() {
      setWeather(null);
      if (!city) return;
      try {
        const resp = await fetch('http://localhost:5010/weather', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ city })
        });
        const data = await resp.json();
        // keep full payload so we can use hourly/daily
        if (data && data.weather) setWeather(data.weather);
      } catch (err) {
        setWeather(null);
      }
    }
    fetchWeather();
  }, [city]);

  const handleSearch = async () => {
    setLoading(true);
    setResults(null);
    try {
      const response = await fetch('http://localhost:5010/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ city, query: neighborhood || category || city })
      });
      const data = await response.json();
      setResults(data);
    } catch (err) {
      setResults({ error: 'Failed to fetch data from Marco.' });
    }
    setLoading(false);
  };

  const suggestionMap = {
    top_food: 'Food',
    historic: 'History',
    transport: 'Public transport',
    markets: 'Shopping',
    family: 'Family',
    events: 'Culture',
    hidden: 'Outdoors',
    coffee: 'Food',
    parks: 'Outdoors'
  };

  const handleSuggestion = async (id) => {
    const mapped = suggestionMap[id] || id;
    // prefer setting category, then run search
    setCategory(mapped);
    // ensure city is set; if empty, don't run automatic search
    if (city) await handleSearch();
  };

  const [generating, setGenerating] = React.useState(false);

  const generateQuickGuide = async () => {
    if (!city || !neighborhood) return;
    setGenerating(true);
    try {
      const resp = await fetch('http://localhost:5010/generate_quick_guide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ city, neighborhood })
      });
      const data = await resp.json();
      if (data && data.quick_guide) {
        setResults({ quick_guide: data.quick_guide, source: data.source, cached: data.cached });
      }
    } catch (err) {
      console.error('generate quick guide failed', err);
    }
    setGenerating(false);
  };

  return (
    <div>
      <Header />
      {/* Weather moved to top so it's visible in the hero area */}
      <div className="hero">
        <div className="hero-inner">
          <div className="logo-wrap">
            {/* Header handles brand image/title */}
          </div>
          <div style={{ flex: 1 }}>
            <h1>TravelLand Neighborhood Explorer</h1>
            <p className="hero-sub">Chat with Marco, your AI travel guide — discover neighborhoods and get recommendations.</p>
          </div>
          <div style={{ minWidth: 220 }}>
            <WeatherDisplay weather={weather} />
          </div>
        </div>
      </div>
      {/* hourly forecast removed to reduce UI data — keep hero focused on current */}
      <div className="app-container">
        <AutocompleteInput
          label="City:"
          options={cityList}
          value={city}
          setValue={val => { setCity(val); setNeighborhood(''); }}
          placeholder="Type or select a city"
        />
        {city && (
          <AutocompleteInput
            label="Neighborhood:"
            options={neighborhoodOptions}
            value={neighborhood}
            setValue={setNeighborhood}
            placeholder="Type or select a neighborhood"
          />
        )}
        {city && neighborhood && generating && (
          <div style={{ margin: '8px 0 12px 0', color: '#3b556f' }}>
            Generating quick guide…
          </div>
        )}
        {city && neighborhoodOptions && neighborhoodOptions.length > 0 && (
          <div className="selector-group">
            <label>Or choose a specific area:</label>
            <NeighborhoodSelect
              options={neighborhoodOptions}
              value={neighborhood}
              onChange={setNeighborhood}
            />
          </div>
        )}
        <SuggestionChips onSelect={handleSuggestion} city={city} />
        <CategoryChips
          categories={categories}
          selectedCategory={category}
          setSelectedCategory={setCategory}
        />
        <button disabled={!city || loading} onClick={handleSearch} style={{ marginTop: 16 }}>Search</button>
        {/* weather is now shown in the hero */}
        {loading && <p>Loading...</p>}
        <SearchResults results={results} />
      </div>
    </div>
  );
}

export default App;
