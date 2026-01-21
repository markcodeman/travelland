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
  'Food', 'Nightlife', 'Culture', 'Outdoors', 'Shopping', 'History'
];

const countries = ['USA', 'Mexico', 'Spain', 'UK', 'France', 'Germany', 'Italy', 'Canada', 'Australia', 'Japan', 'China', 'India', 'Brazil', 'Argentina', 'South Africa', 'Netherlands', 'Portugal', 'Sweden', 'Norway', 'Denmark', 'Iceland'];

const popularCities = ['New York', 'London', 'Paris', 'Tokyo', 'Sydney', 'Rio de Janeiro', 'Lisbon', 'Reykjavik', 'Berlin', 'Rome', 'Barcelona', 'Amsterdam', 'Vienna', 'Prague', 'Budapest', 'Warsaw', 'Athens', 'Istanbul', 'Cairo', 'Cape Town', 'Mumbai', 'Bangkok', 'Singapore', 'Seoul', 'Beijing', 'Shanghai', 'Hong Kong', 'Dubai', 'Moscow', 'Saint Petersburg', 'Madrid', 'Milan', 'Venice', 'Florence', 'Vienna', 'Salzburg', 'Innsbruck', 'Zurich', 'Geneva', 'Interlaken', 'Copenhagen', 'Stockholm', 'Oslo', 'Helsinki', 'Tallinn', 'Riga', 'Vilnius', 'Krakow', 'Budapest', 'Bucharest', 'Sofia', 'Belgrade', 'Zagreb', 'Ljubljana', 'Sarajevo', 'Skopje', 'Tirana', 'Podgorica', 'Pristina', 'Bratislava', 'Brno', 'Prague', 'Warsaw', 'Gdansk', 'Krakow', 'Wroclaw', 'Poznan', 'Lodz', 'Katowice', 'Bydgoszcz', 'Lublin', 'Bialystok', 'Gdansk', 'Szczecin', 'Olsztyn', 'Rzeszow', 'Kielce', 'Zielona Gora', 'Opole', 'Czestochowa', 'Gliwice', 'Zabrze', 'Bielsko-Biala', 'Ruda Slaska', 'Rybnik', 'Tychy', 'Dabrowa Gornicza', 'Chorzow', 'Walbrzych', 'Wloclawek', 'Tarnow', 'Plock', 'Elblag', 'Torun', 'Kalisz', 'Koszalin', 'Legnica', 'Grudziadz', 'Slupsk', 'Jaworzno', 'Jastrzebie-Zdroj', 'Tarnowskie Gory', 'Piekary Slaskie', 'Rumia', 'Wejherowo', 'Sopot', 'Gdynia', 'Slupsk', 'Koszalin', 'Swinoujscie', 'Kolobrzeg', 'Miedzyzdroje', 'Ustka', 'Leba', 'Jastarnia', 'Wladyslawowo', 'Hel', 'Krynica Morska', 'Frombork', 'Malbork', 'Gdansk', 'Gdynia', 'Sopot', 'Rumia', 'Reda', 'Wejherowo', 'Kartuzy', 'Koscierzyna', 'Bytow', 'Człuchów', 'Chojnice', 'Tczew', 'Starogard Gdanski', 'Skarszewy', 'Pelplin', 'Tczew', 'Sztum', 'Dzierzgon', 'Prabuty', 'Kwidzyn', 'Grudziadz', 'Swiecie', 'Chełmno', 'Torun', 'Wloclawek', 'Lipno', 'Rypin', 'Golabki', 'Brodnica', 'Jablonowo Pomorskie', 'Nowe Miasto Lubawskie', 'Olsztyn', 'Dobre Miasto', 'Lidzbark Warminski', 'Bartoszyce', 'Ketrzyn', 'Mragowo', 'Pisz', 'Szczytno', 'Ostroda', 'Ilawa', 'Nowy Dwor Gdanski', 'Morag', 'Paslek', 'Elblag', 'Tolkmicko', 'Frombork', 'Braniewo', 'Lidzbark Warminski', 'Bartoszyce', 'Ketrzyn', 'Mragowo', 'Pisz', 'Szczytno', 'Ostroda', 'Ilawa', 'Nowy Dwor Gdanski', 'Morag', 'Paslek', 'Elblag', 'Tolkmicko', 'Frombork', 'Braniewo', 'Lidzbark Warminski', 'Bartoszyce', 'Ketrzyn', 'Mragowo', 'Pisz', 'Szczytno', 'Ostroda', 'Ilawa', 'Nowy Dwor Gdanski', 'Morag', 'Paslek', 'Elblag', 'Tolkmicko', 'Frombork', 'Braniewo'];

function App() {
  const [city, setCity] = useState('');
  const [country, setCountry] = useState('');
  const [neighborhood, setNeighborhood] = useState('');
  const [neighborhoodOptions, setNeighborhoodOptions] = useState([]);
  const [category, setCategory] = useState('');
  const [generating, setGenerating] = useState(false);
  const [weather, setWeather] = useState(null);
  const [weatherError, setWeatherError] = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('Loading...');
  const [selectedSuggestion, setSelectedSuggestion] = useState('');

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
            // remove duplicate neighborhood names while preserving order
            const uniqueNames = Array.from(new Set(names));
            // Add fallback popular neighborhoods to ensure common ones are included
            const fallback = {
              'Rio de Janeiro': ['Copacabana', 'Ipanema', 'Leblon', 'Santa Teresa', 'Barra da Tijuca', 'Lapa', 'Botafogo', 'Jardim Botânico', 'Gamboa', 'Leme', 'Vidigal'],
              'London': ['Camden', 'Chelsea', 'Greenwich', 'Soho', 'Shoreditch'],
              'New York': ['Manhattan', 'Brooklyn', 'Harlem', 'Queens', 'Bronx'],
              'Lisbon': ['Baixa', 'Chiado', 'Alfama', 'Bairro Alto', 'Belém']
            };
            const fallbackNames = fallback[city] || [];
            const allNames = Array.from(new Set([...uniqueNames, ...fallbackNames]));
            setNeighborhoodOptions(allNames);
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
          body: JSON.stringify({ query: city })
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

  // When a neighborhood is selected, generate a neighborhood-scoped quick guide
  useEffect(() => {
    let mounted = true;
    const timer = setTimeout(async () => {
      if (!city || !neighborhood) return;
      try {
        setGenerating(true);
        const resp = await fetch('http://localhost:5010/generate_quick_guide', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ city, neighborhood })
        });
        if (!resp.ok) throw new Error('Generate request failed');
        const data = await resp.json();
        if (typeof data !== 'object' || data === null) throw new Error('Invalid generate response');
        if (!mounted) return;
        if (data && data.quick_guide) {
          const resObj = { quick_guide: data.quick_guide, source: data.source, cached: data.cached, source_url: data.source_url };
          if (data.mapillary_images) resObj.mapillary_images = data.mapillary_images;
          if (!category) {
            setResults(resObj);
          }
        }
      } catch (err) {
        console.error('Generate quick guide failed', err);
      } finally {
        setGenerating(false);
      }
    }, 250);
    return () => { mounted = false; clearTimeout(timer); };
  }, [city, neighborhood]);

  // Fetch weather when city (or neighborhood) changes — prefer lat/lon by calling /geocode first
  useEffect(() => {
    async function fetchWeather() {
      setWeather(null);
      setWeatherError(null);
      if (!city) return;
      try {
        // ask the backend to resolve coordinates for the city/neighborhood
        const gresp = await fetch('http://localhost:5010/geocode', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ city, neighborhood })
        });
        if (!gresp.ok) {
          // backend may not have /geocode available (404). Fall back to the previous
          // behavior of POSTing city to /weather so the app keeps working.
          try {
            const fallbackResp = await fetch('http://localhost:5010/weather', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ city })
            });
            if (fallbackResp.ok) {
              const fdata = await fallbackResp.json();
              if (fdata && fdata.weather) {
                setWeather(fdata.weather);
                return;
              }
            }
            setWeatherError('Unable to determine coordinates for this location. Try a different neighborhood or search.');
          } catch (e) {
            setWeatherError('Unable to determine coordinates for this location. Try a different neighborhood or search.');
          }
          return;
        }
        const gdata = await gresp.json();
        if (gdata.display_name) {
          const parts = gdata.display_name.split(', ');
          setCountry(parts[parts.length - 1]);
        }
        const lat = gdata && (gdata.lat || gdata.latitude);
        const lon = gdata && (gdata.lon || gdata.longitude || gdata.lng);
        if (!lat || !lon) {
          setWeatherError('Could not find coordinates for this location.');
          return;
        }

        const resp = await fetch('http://localhost:5010/weather', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lat: Number(lat), lon: Number(lon) })
        });
        if (!resp.ok) {
          setWeatherError('Weather service is temporarily unavailable. Please try again.');
          return;
        }
        const data = await resp.json();
        if (data && data.weather) {
          setWeather(data.weather);
        } else {
          setWeatherError('No weather data available for this location.');
        }
      } catch (err) {
        console.error('fetchWeather error', err);
        setWeatherError('Failed to fetch weather. Check your connection or try again.');
        setWeather(null);
      }
    }
    fetchWeather();
  }, [city, neighborhood]);

  const suggestionMap = {
    transport: 'Public transport',
    hidden: 'Hidden gems',
    coffee: 'Coffee & tea',
  };



  const handleSuggestion = async (id) => {
    const mapped = suggestionMap[id] || id;
    // prefer setting category, then run search
    setCategory(mapped);
    setSelectedSuggestion(id);
    // ensure city is set; if empty, don't run automatic search
    if (city) await handleSearch(mapped);
  };

  const handleSearch = async (overrideCategory) => {
    if (!city || !String(city).trim()) { setWeatherError('Please select a city before searching.'); return; }
    // Set loading message
    let displayCategory = overrideCategory || category;
    let msg = 'Loading...';
    if (displayCategory && neighborhood) {
      msg = `Hang tight brewing up ${displayCategory} in ${neighborhood}, ${city}`;
    } else if (displayCategory) {
      msg = `Hang tight brewing up ${displayCategory} in ${city}`;
    } else if (neighborhood) {
      msg = `Hang tight exploring ${neighborhood}, ${city}`;
    } else {
      msg = `Hang tight exploring ${city}`;
    }
    setLoadingMessage(msg);
    setLoading(true);
    setWeatherError(null);
    try {
      // Geocode with city and country
      const gresp = await fetch('http://localhost:5010/geocode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ city, neighborhood: '', country })
      });
      if (!gresp.ok) {
        setWeatherError('Geocode failed: Could not find the location.');
        return;
      }
      const gdata = await gresp.json();
      const lat = gdata.lat;
      const lon = gdata.lon;
      // Update country from geocode result
      if (gdata.display_name) {
        const parts = gdata.display_name.split(', ');
        setCountry(parts[parts.length - 1]);
      }
      // Fetch neighborhoods
      try {
        const resp = await fetch(`http://localhost:5010/neighborhoods?lat=${lat}&lon=${lon}&lang=en`);
        const data = await resp.json();
        if (data && Array.isArray(data.neighborhoods) && data.neighborhoods.length > 0) {
          const names = data.neighborhoods.map(n => n.name || n.display_name || n.label || n.id).filter(Boolean);
          const uniqueNames = Array.from(new Set(names));
          setNeighborhoodOptions(uniqueNames);
        } else {
          const fallback = {
            'Rio de Janeiro': ['Copacabana', 'Ipanema', 'Leblon', 'Santa Teresa', 'Barra da Tijuca', 'Lapa', 'Botafogo', 'Jardim Botânico', 'Gamboa', 'Leme', 'Vidigal'],
            'London': ['Camden', 'Chelsea', 'Greenwich', 'Soho', 'Shoreditch'],
            'New York': ['Manhattan', 'Brooklyn', 'Harlem', 'Queens', 'Bronx'],
            'Lisbon': ['Baixa', 'Chiado', 'Alfama', 'Bairro Alto', 'Belém'],
            'Reykjavik': ['Miðborg', 'Vesturbær', 'Hlíðar', 'Laugardalur', 'Háaleiti']
          };
          setNeighborhoodOptions(fallback[city] || []);
        }
      } catch (err) {
        // ignore
      }
      // Fetch weather
      try {
        const wresp = await fetch('http://localhost:5010/weather', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lat, lon })
        });
        if (wresp.ok) {
          const wdata = await wresp.json();
          setWeather(wdata.weather);
        } else {
          setWeatherError('Weather fetch failed.');
        }
      } catch (e) {
        setWeatherError('Weather fetch failed.');
      }
      // Fetch quick guide
      try {
        // Backend expects `query` for the city and `category` for the search term
        const searchPayload = { query: city };
        if (neighborhood) searchPayload.neighborhood = neighborhood;
        let q = overrideCategory || category;
        if (q) searchPayload.category = q;
        console.debug('search payload', searchPayload);
        const qresp = await fetch('http://localhost:5010/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(searchPayload)
        });
        const qdata = await qresp.json();
        console.debug('search response', qdata);
        if (qdata && qdata.error) {
          setWeatherError(qdata.error + (qdata.debug_info ? ` — ${JSON.stringify(qdata.debug_info)}` : ''));
        } else if (qdata && (qdata.quick_guide || qdata.summary || qdata.quickGuide || qdata.wikivoyage || qdata.venues || qdata.costs)) {
          setResults(qdata);
        }
      } catch (err) {
        console.error('search quick guide failed', err);
      }
    } catch (e) {
      setWeatherError('Search failed.');
    } finally {
      setLoading(false);
    }
  };

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

      {/* Header restored */}
      <Header />
      <div style={{ minWidth: 220, margin: '0 auto', maxWidth: 600 }}>
        <WeatherDisplay weather={weather} city={city} />
        {weatherError && (
          <div style={{ marginTop: 8, color: '#9b2c2c', fontSize: 13 }}>
            {weatherError}
          </div>
        )}
      </div>
      {/* hourly forecast removed to reduce UI data — keep hero focused on current */}
      <div className="app-container">
        <AutocompleteInput
          label="City:"
          options={popularCities}
          value={city}
          setValue={setCity}
          placeholder="Type or select a city"
        />
        <div style={{ marginTop: 8 }}>
          <label style={{ display: 'block', marginBottom: 4 }}>Country:</label>
          <select value={country} onChange={(e) => setCountry(e.target.value)} style={{ width: '100%', padding: 8, border: '1px solid #ccc', borderRadius: 4 }}>
            <option value="">Select Country (optional)</option>
            {countries.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div style={{ marginTop: 8 }}>
          <button onClick={handleSearch} disabled={loading} style={{ padding: '8px 16px', background: '#007bff', color: 'white', border: 'none', borderRadius: 4, cursor: loading ? 'not-allowed' : 'pointer' }}>
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
        {neighborhoodOptions.length > 0 && (
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
        {loading && <p>{loadingMessage}</p>}
        <SearchResults results={results} />
      </div>
    </div>
  );
}

export default App;
