import { useEffect, useState } from 'react';
import './FunFact.css';

// Fallback fun facts for major cities
const FALLBACK_FACTS = {
  'paris': [
    "Paris was originally a Roman city called 'Lutetia'.",
    "The Eiffel Tower was supposed to be dismantled after 20 years.",
    "There is only one stop sign in the entire city of Paris."
  ],
  'london': [
    "Big Ben is actually the name of the bell, not the clock tower.",
    "London has been inhabited for over 2,000 years.",
    "The London Underground is the oldest underground railway in the world."
  ],
  'new york': [
    "New York City was originally called New Amsterdam.",
    "There are over 800 languages spoken in NYC.",
    "The Statue of Liberty was a gift from France in 1886."
  ],
  'tokyo': [
    "Tokyo was formerly known as Edo.",
    "Shibuya Crossing is the busiest pedestrian crossing in the world.",
    "Tokyo has the most Michelin-starred restaurants of any city."
  ],
  'default': [
    "Cities are complex ecosystems with layers of history, architecture, and diverse communities.",
    "Urban geography studies how cities grow, adapt, and define their regional identity.",
    "Every urban center has a unique topological layout influenced by its local environment."
  ]
};

const getFallbackFact = (city) => {
  const cityKey = city.toLowerCase().trim();
  const facts = FALLBACK_FACTS[cityKey] || FALLBACK_FACTS['default'];
  return facts[Math.floor(Math.random() * facts.length)];
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
  const localSpiceUp = (text, style, variant = 'A') => {
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
  };

  // Paraphrase using Groq if available, otherwise use local spice-up
  const spiceFact = async (text) => {
    if (!text) return;
    setSpiceLoading(true);
    setSpiceSource(null);
    setSpicedFact(null);

    // Decide whether the original sentence is factual (numbers, 'capital', 'population', etc.)
    const factualRe = /\b(capital|population|km|kilometer|km²|founded|established|born|\d{3,4}|year|largest|oldest|known for|historic)\b/i;
    const isFactual = factualRe.test(text || '');

    // Detect and block "teasers"
    const teaserRe = /\b(explore|discover|special|hidden gems|secret|wanna know|trip|visit|amazing)\b/i;
    const isTease = teaserRe.test(text || '') && !isFactual;

    if (isTease && !isFactual) {
      console.log("[FUN-FACT] Rejecting tease-only source fact.");
      setSpicedFact(text); // Just show it as is, or maybe we should just not show the component?
      // For now, let's just let it be, but prefer nerdy to drown out the fluffiness.
    }

    const styles = ['punchy', 'slang', 'nerdy'];
    let style;
    if (isFactual) {
      // Favor factual styles for factual source sentences
      style = Math.random() < 0.8 ? 'nerdy' : 'punchy';
    } else {
      style = 'nerdy'; // Force nerdy if it feels fluffy
    }

    const variant = (Math.random() < 0.5) ? 'A' : 'B';
    setSpiceStyle(style);

    try {
      // Check if Groq LLM is available on server
      const enResp = await fetch('/api/groq-enabled');
      const en = enResp.ok ? await enResp.json() : { groq_enabled: false };
      if (en.groq_enabled) {
        // Ask the LLM to paraphrase strictly
        const resp = await fetch('/api/llm-paraphrase', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, style })
        });
        if (resp.ok) {
          const j = await resp.json();
          if (j.paraphrase) {
            // Client-side safety: reject paraphrases that contain disallowed language
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
      }

      // Fallback to local templates
      setSpicedFact(localSpiceUp(text, style, variant));
      setSpiceSource('local');
    } catch (e) {
      console.warn('Spice failed, using local:', e);
      setSpicedFact(localSpiceUp(text, style, variant));
      setSpiceSource('local');
    } finally {
      setSpiceLoading(false);
    }
  };

  useEffect(() => {
    if (!city) return;

    const fetchFunFact = async () => {
      setLoading(true);
      setError(null);
      
      try {
        console.log(`[FUN-FACT] Fetching fun fact for: ${city}`);
        
        // Add timeout to prevent hanging
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);
        
        const response = await fetch('/api/fun-fact', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ city }),
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);

        let original = null;
        if (response.ok) {
          const data = await response.json();
          console.log(`[FUN-FACT] Received:`, data);
          original = data.funFact || getFallbackFact(city);
        } else {
          console.warn(`[FUN-FACT] HTTP error: ${response.status}`);
          original = getFallbackFact(city);
        }

        setFunFact(original);
        // Immediately spice it up (prefer LLM 'nerdy')
        spiceFact(original);

      } catch (err) {
        console.error('[FUN-FACT] Failed to fetch:', err);
        const fallback = getFallbackFact(city);
        setFunFact(fallback);
        spiceFact(fallback);
      } finally {
        setLoading(false);
      }
    };

    fetchFunFact();
  }, [city]);

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

export default FunFact;
