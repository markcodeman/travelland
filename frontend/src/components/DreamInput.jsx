import React, { useState, useEffect, useRef } from 'react';
import './DreamInput.css';

const DREAM_PROMPTS = [
  "Enter a city name (Paris, Tokyo, Barcelona...)",
  "Which city calls to you? (London, New York, Rome...)",
  "Tell me your destination city...",
  "What city would you like to explore?",
  "Which city beckons you?"
];

const DreamInput = ({ onLocationChange, onCityGuide, canTriggerCityGuide }) => {
  const [dreamInput, setDreamInput] = useState('');
  const [currentPrompt, setCurrentPrompt] = useState(DREAM_PROMPTS[0]);
  const [isAnimating, setIsAnimating] = useState(false);
  const [sparkles, setSparkles] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef(null);

  // Rotate prompts every 8 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentPrompt(prev => {
        const currentIndex = DREAM_PROMPTS.indexOf(prev);
        return DREAM_PROMPTS[(currentIndex + 1) % DREAM_PROMPTS.length];
      });
    }, 8000);

    return () => clearInterval(interval);
  }, []);

  // Create sparkle effect
  const createSparkle = (x, y) => {
    const newSparkle = {
      id: Date.now() + Math.random(),
      x,
      y,
      size: Math.random() * 20 + 10,
      duration: Math.random() * 1000 + 500
    };
    
    setSparkles(prev => [...prev, newSparkle]);
    
    // Remove sparkle after animation
    setTimeout(() => {
      setSparkles(prev => prev.filter(s => s.id !== newSparkle.id));
    }, newSparkle.duration);
  };

  // Wand wave animation
  const performWandAnimation = () => {
    setIsAnimating(true);
    setIsProcessing(true);
    
    // Create multiple sparkles around the input
    const rect = inputRef.current?.getBoundingClientRect();
    if (rect) {
      for (let i = 0; i < 8; i++) {
        setTimeout(() => {
          const x = rect.left + Math.random() * rect.width;
          const y = rect.top + Math.random() * rect.height;
          createSparkle(x, y);
        }, i * 100);
      }
    }

    // Reset animation after completion
    setTimeout(() => {
      setIsAnimating(false);
      setIsProcessing(false);
    }, 1500);
  };

  // Parse natural language input
  const parseDreamInput = async (input) => {
    if (!input.trim()) return null;

    try {
      const response = await fetch('/api/parse-dream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input })
      });

      if (!response.ok) throw new Error('Parsing failed');
      
      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Failed to parse dream input:', error);
      return null;
    }
  };

  // Handle dream submission
  const handleDreamSubmit = async (e) => {
    e.preventDefault();
    
    if (!dreamInput.trim() || isProcessing) return;

    // Quick client-side validation for city names
    const input = dreamInput.trim();
    const commonCities = ['paris', 'tokyo', 'london', 'new york', 'barcelona', 'rome', 'amsterdam', 'berlin', 'lisbon', 'sydney', 'dubai', 'singapore', 'bangkok', 'mumbai', 'toronto', 'vancouver', 'mexico city', 'buenos aires', 'cape town', 'cairo', 'istanbul', 'moscow', 'madrid', 'prague', 'vienna', 'budapest', 'stockholm', 'oslo', 'helsinki', 'copenhagen', 'warsaw', 'athens', 'dublin', 'reykjavik'];
    
    const isLikelyCity = commonCities.some(city => input.toLowerCase().includes(city)) || 
                        /^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$/.test(input) && // Title case pattern
                        input.split(' ').length <= 3; // Max 3 words

    if (!isLikelyCity) {
      alert('Please enter a specific city name (e.g., Paris, Tokyo, Barcelona). Regions like "Swiss Alps" should be entered as their nearest city (e.g., Zurich).');
      return;
    }

    performWandAnimation();

    const parsed = await parseDreamInput(dreamInput);
    
    if (parsed) {
      // Update parent with parsed location
      onLocationChange({
        country: parsed.country || '',
        state: parsed.state || '',
        city: parsed.city || '',
        neighborhood: parsed.neighborhood || '',
        countryName: parsed.countryName || '',
        stateName: parsed.stateName || '',
        cityName: parsed.cityName || parsed.city || '',
        neighborhoodName: parsed.neighborhoodName || parsed.neighborhood || '',
        intent: parsed.intent || ''
      });

      // Trigger city guide immediately after location change
      if (parsed.city && canTriggerCityGuide) {
        setTimeout(() => onCityGuide(), 800);
      }
    }
  };

  // Handle input focus with sparkles
  const handleInputFocus = () => {
    const rect = inputRef.current?.getBoundingClientRect();
    if (rect) {
      createSparkle(rect.right - 20, rect.top);
      createSparkle(rect.left + 20, rect.bottom);
    }
  };

  // Fetch location suggestions based on partial input
  const fetchSuggestions = async (input) => {
    if (input.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    try {
      const response = await fetch('/api/location-suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input })
      });

      if (response.ok) {
        const data = await response.json();
        setSuggestions(data.suggestions || []);
        setShowSuggestions(true);
      }
    } catch (error) {
      console.error('Failed to fetch suggestions:', error);
    }
  };

  // Handle input change with suggestions
  const handleInputChange = (e) => {
    const value = e.target.value;
    setDreamInput(value);
    fetchSuggestions(value);
  };

  // Handle suggestion selection
  const handleSuggestionClick = (suggestion) => {
    setDreamInput(suggestion.display_name);
    setShowSuggestions(false);
    // Log successful suggestion for learning
    fetch('/api/log-suggestion-success', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ suggestion: suggestion.display_name })
    });
  };

  return (
    <div className="dream-input-container">
      {/* Sparkle effects */}
      {sparkles.map(sparkle => (
        <div
          key={sparkle.id}
          className="sparkle"
          style={{
            left: sparkle.x,
            top: sparkle.y,
            width: sparkle.size,
            height: sparkle.size,
            animationDuration: `${sparkle.duration}ms`
          }}
        />
      ))}

      {/* Magical title with prompt rotation */}
      <div className="dream-title">
        <div className="prompt-text">
          {currentPrompt}
          <div className="prompt-dots">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </div>
        </div>
      </div>

      {/* Dream input form */}
      <form onSubmit={handleDreamSubmit} className="dream-form">
        <div className="input-wrapper">
          <input
            ref={inputRef}
            type="text"
            value={dreamInput}
            onChange={handleInputChange}
            onFocus={handleInputFocus}
            placeholder="City name (required): Paris, Tokyo, Barcelona..."
            className={`dream-input ${isAnimating ? 'wand-waving' : ''}`}
            disabled={isProcessing}
          />
          
          {/* Location suggestions dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <div className="suggestions-dropdown">
              {suggestions.map((suggestion, index) => (
                <div
                  key={index}
                  className="suggestion-item"
                  onClick={() => handleSuggestionClick(suggestion)}
                >
                  <span className="suggestion-name">{suggestion.display_name}</span>
                  <span className="suggestion-detail">{suggestion.detail}</span>
                </div>
              ))}
            </div>
          )}

          {/* Magical wand button */}
          <button
            type="submit"
            className={`wand-button ${isAnimating ? 'waving' : ''}`}
            disabled={!dreamInput.trim() || isProcessing}
            title="Make it magical!"
          >
            <span className="wand-icon">🪄</span>
          </button>
        </div>

        {/* Processing indicator */}
        {isProcessing && (
          <div className="processing-text">
            <span className="processing-dots">
              <span>•</span>
              <span>•</span>
              <span>•</span>
            </span>
            Weaving your travel dreams...
          </div>
        )}

        {/* Helper text */}
        <div className="dream-helper">
          ✨ Describe your perfect destination in natural language
        </div>
      </form>

      {/* Location display when parsed */}
      {dreamInput && (
        <div className="parsed-location">
          <div className="location-preview">
            📍 Your dream destination awaits...
          </div>
        </div>
      )}
    </div>
  );
};

export default DreamInput;
