import { memo, useCallback, useEffect, useMemo, useState } from 'react';

const CitySuggestions = ({ city, neighborhood, onCategorySelect, searchResults }) => {
  const categories = useMemo(() => (
    Array.isArray(searchResults?.categories) ? searchResults.categories : []
  ), [searchResults?.categories]);

  console.log('CitySuggestions DEBUG:', { 
    city, 
    neighborhood,
    searchResults,
    hasCategories: categories.length > 0,
    categoriesLength: categories.length,
    firstCategory: categories[0]
  });

  const pickIcon = useCallback((label) => {
    const text = (label || '').toLowerCase();
    if (text.includes('food') || text.includes('dining') || text.includes('cuisine')) return '🍴';
    if (text.includes('culture') || text.includes('art') || text.includes('museum')) return '🎨';
    if (text.includes('nightlife') || text.includes('bar') || text.includes('club')) return '🌙';
    if (text.includes('shopping') || text.includes('market')) return '🛍️';
    if (text.includes('park') || text.includes('nature') || text.includes('garden')) return '🌳';
    if (text.includes('historic') || text.includes('heritage') || text.includes('castle')) return '🏛️';
    if (text.includes('beach') || text.includes('water') || text.includes('coast')) return '🏖️';
    if (text.includes('music') || text.includes('theatre') || text.includes('shows')) return '🎭';
    return '📍';
  }, []);

  // Map categories from backend into usable suggestions, memoized to avoid recompute
  const suggestions = useMemo(() => (
    categories
      .map((c) => {
        if (!c) return null;
        if (typeof c === 'string') {
          return {
            label: c,
            intent: c.toLowerCase(),
            icon: pickIcon(c),
          };
        }
        const label = c.label || c.category || c.name || '';
        if (!label) return null;
        return {
          label,
          intent: c.intent || label.toLowerCase(),
          icon: c.icon || pickIcon(label),
        };
      })
      .filter(Boolean)
  ), [categories, pickIcon]);

  // Don't show anything if no real categories exist
  if (!city || suggestions.length === 0) {
    return null;
  }

  // Dynamic heading based on whether neighborhood is selected
  const getLocationText = () => {
    if (neighborhood) {
      return `${neighborhood}, ${city}`;
    }
    return city;
  };

  return (
    <div className="text-center space-y-4">
      <h3 className="text-xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-brand-orange to-brand-aqua">
        ✨ What interests you in {getLocationText()}?
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 max-w-4xl mx-auto">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            className="flex flex-col items-center gap-1 px-4 py-3 rounded-xl border border-slate-200 bg-white shadow-sm hover:border-brand-orange hover:shadow-md transition"
            onClick={() => onCategorySelect(suggestion.intent, suggestion.label)}
          >
            <span className="text-2xl">{suggestion.icon}</span>
            <span className="text-sm font-semibold text-slate-800">{suggestion.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

// Helper for fallback facts (simple inline, can be expanded later)
const getFallbackFact = (city) => `Explore the vibrant city of ${city}!`;

// Helper for Wikipedia summary
const fetchWikipediaSummary = async (city) => {
  try {
    const response = await fetch(`/api/fun-fact`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ city })
    });
    if (response.ok) {
      const data = await response.json();
      return data.funFact || data.facts?.[0] || null;
    }
  } catch (e) {
    console.warn('fetchWikipediaSummary failed:', e);
  }
  return null;
};

const FunFact = ({ city }) => {
  const [funFact, setFunFact] = useState(null);
  const [spicedFact, setSpicedFact] = useState(null);
  const [spiceLoading, setSpiceLoading] = useState(false);
  const [spiceSource, setSpiceSource] = useState(null); // 'ai' or 'local'
  const [spiceStyle, setSpiceStyle] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Local lightweight paraphrase fallback (safe: uses same text, no new facts)
  const localSpiceUp = useCallback((text, style, variant = 'A') => {
    const base = text.replace(/\s+/g, ' ').trim();
    const templates = {
      punchy: {
        A: [`⚡ Quick Fact: ${base}`, `📍 Local Note: ${base}`, `⚡ Spotlight: ${base}`],
        B: [`⚡ City Tip: ${base}`, `🏙️ Insight: ${base}`, `🌟 Note: ${base}`]
      },
      slang: {
        A: [`🎒 Local Lowdown: ${base}`, `🗣️ Street Truth: ${base}`, `📣 Word is: ${base}`],
        B: [`🔥 Hot Take: ${base}`, `👟 On the Ground: ${base}`, `📢 Heads Up: ${base}`]
      },
      nerdy: {
        A: [`🧠 Nerd Note: ${base}`, `📚 Data Point: ${base}`, `🔎 Deep Dive: ${base}`],
        B: [`🛰️ Tech Spec: ${base}`, `🔬 Fact Check: ${base}`, `📊 Stat: ${base}`]
      }
    };
    const pool = (templates[style] && templates[style][variant]) || templates['nerdy']['A'];
    return pool[Math.floor(Math.random() * pool.length)];
  }, []);

  // Paraphrase using Groq if available, otherwise use local spice-up
  const spiceFact = useCallback(async (text) => {
    if (!text || typeof text !== 'string' || !text.trim()) {
      setSpicedFact('');
      setSpiceSource(null);
      return;
    }
    const trimmed = text.trim();
    if (trimmed.length < 8) {
      const fallback = localSpiceUp(trimmed, 'nerdy', 'A');
      setSpicedFact(fallback);
      setSpiceSource('local');
      return;
    }
    setSpiceLoading(true);
    setSpiceSource(null);
    setSpicedFact(null);

    const factualRe = /\b(capital|population|km|kilometer|km²|founded|established|created|known for|historic)\b/i;
    const isFactual = factualRe.test(text || '');
    const teaserRe = /\b(explore|discover|special|hidden gems|secret|wanna know|trip|visit|amazing)\b/i;
    const isTease = teaserRe.test(text || '') && !isFactual;
    if (isTease && !isFactual) {
      console.log("[FUN-FACT] Rejecting tease-only source fact.");
      setSpicedFact(text);
    }
    const styles = ['punchy', 'slang', 'nerdy'];
    const style = isFactual ? (Math.random() < 0.8 ? 'nerdy' : 'punchy') : 'nerdy';
    const variant = Math.random() < 0.5 ? 'A' : 'B';
    setSpiceStyle(style);
    try {
      const enResp = await fetch('/api/groq-enabled');
      const en = enResp.ok ? await enResp.json() : { groq_enabled: false };
      if (en.groq_enabled) {
        const resp = await fetch('/api/llm-paraphrase', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: trimmed, style: style || 'nerdy' })
        });
        if (!resp.ok) {
          console.warn('[FUN-FACT] llm-paraphrase returned non-200:', resp.status);
          setSpicedFact(localSpiceUp(text, style, variant));
          setSpiceSource('local');
          return;
        }
        const j = await resp.json();
        if (j.paraphrase) {
          const badRe = /\b(?:fuck|shit|bitch|cunt|asshole|motherfucker)\b/i;
          if (badRe.test(j.paraphrase || '')) {
            console.warn('LLM paraphrase contained disallowed language; falling back to local template');
            setSpicedFact(localSpiceUp(text, style, variant));
            setSpiceSource('local');
            return;
          }
          setSpicedFact(j.paraphrase);
          setSpiceSource('ai');
          return;
        }
      }
      setSpicedFact(localSpiceUp(text, style, variant));
      setSpiceSource('local');
    } catch (e) {
      console.warn('Spice failed, using local:', e);
      setSpicedFact(localSpiceUp(text, style, variant));
      setSpiceSource('local');
    } finally {
      setSpiceLoading(false);
    }
  }, [localSpiceUp]);

  useEffect(() => {
    if (!city) return;
    const fetchFunFact = async () => {
      setLoading(true);
      setError(null);
      try {
        console.log(`[FUN-FACT] Fetching fun fact for: ${city}`);
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);
        const response = await fetch('/api/fun-fact', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ city }),
          signal: controller.signal
        });
        clearTimeout(timeoutId);
        let original = null;
        if (response.ok) {
          const data = await response.json();
          console.log(`[FUN-FACT] Received:`, data);
          if (Array.isArray(data.facts) && data.facts.length) {
            original = data.facts.join(' ');
          } else {
            original = data.funFact || getFallbackFact(city);
          }
        } else {
          console.warn(`[FUN-FACT] HTTP error: ${response.status}`);
          const wiki = await fetchWikipediaSummary(city);
          original = wiki || getFallbackFact(city);
        }
        setFunFact(original);
        spiceFact(original);
      } catch (err) {
        console.error('[FUN-FACT] Failed to fetch:', err);
        const fallback = (await fetchWikipediaSummary(city)) || getFallbackFact(city);
        setFunFact(fallback);
        spiceFact(fallback);
      } finally {
        setLoading(false);
      }
    };
    fetchFunFact();
  }, [city, spiceFact]);

  if (!city) return null;
  if (loading) return (
    <div className="fun-fact fun-fact--loading">
      <div className="fun-fact-header">
        <span className="fun-fact-icon">💡</span>
        <span className="fun-fact-title">FUN FACT</span>
      </div>
      <div className="fun-fact-loading">
        <div className="fun-fact-shimmer"></div>
      </div>
    </div>
  );
  if (!funFact && !spicedFact) return null;
  const display = spicedFact || funFact;
  const indicator = spiceSource ? (spiceSource === 'ai' ? `Auto-spiced (AI: ${spiceStyle})` : `Auto-spiced (local: ${spiceStyle})`) : '';
  return (
    <div className="fun-fact">
      <div className="fun-fact-header">
        <span className="fun-fact-icon">💡</span>
        <span className="fun-fact-title">FUN FACT about {city.toUpperCase()}</span>
      </div>
      <div className="fun-fact-content">
        {display}
      </div>
      {indicator && (
        <div style={{ marginTop: 8 }}>
          <small style={{ color: '#888' }}>{indicator}{spiceLoading ? ' — Working…' : ''}</small>
        </div>
      )}
    </div>
  );
};

export default memo(CitySuggestions);
