import React, { useState, useEffect, useRef } from 'react';
import './DreamInput.css';
import PixabayImage from './PixabayImage';

const DREAM_PROMPTS = [
  "Which city calls to you? (Paris, Tokyo, Barcelona...)",
  "Tell me your destination city...",
  "What city would you like to explore?",
  "Which city beckons you?",
  "Enter your dream destination..."
];

const DreamInput = ({ onLocationChange, onCityGuide, canTriggerCityGuide }) => {
  const [dreamInput, setDreamInput] = useState('');
  const [currentPrompt, setCurrentPrompt] = useState(DREAM_PROMPTS[0]);
  const [isAnimating, setIsAnimating] = useState(false);
  const [sparkles, setSparkles] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [heroImage, setHeroImage] = useState(null);
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

  // Fetch hero image for city
  const fetchHeroImage = async (city) => {
    try {
      const response = await fetch('/api/pixabay/hero-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ city })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.image) {
          setHeroImage(data.image);
        }
      }
    } catch (error) {
      console.error('Failed to fetch hero image:', error);
    }
  };

  // Parse natural language input - now simplified to city extraction only
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
      // Fallback: treat input as simple city name
      return {
        city: input.trim(),
        country: '',
        state: '',
        intent: '' // No intent parsing - just city
      };
    }
  };

  // Handle dream submission with immediate city guide display
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
      // Fetch hero image for the city
      if (parsed.city) {
        fetchHeroImage(parsed.city);
      }
      
      // Update parent with parsed location
      onLocationChange({
        country: parsed.country || '',
        state: parsed.state || '',
        city: parsed.city || '',
        intent: parsed.intent || ''
      });
      
      // Trigger city guide with the parsed city directly
      if (parsed.city) {
        setTimeout(() => onCityGuide(parsed.city), 1000);
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
        const suggestions = data.suggestions || [];
        
        // Fetch thumbnails for each suggestion
        const suggestionsWithImages = await Promise.all(
          suggestions.map(async (suggestion) => {
            try {
              const thumbnailResponse = await fetch('/api/pixabay/thumbnails', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ city: suggestion.display_name, count: 1 })
              });
              
              if (thumbnailResponse.ok) {
                const thumbnailData = await thumbnailResponse.json();
                return {
                  ...suggestion,
                  thumbnail: thumbnailData.thumbnails[0] || null
                };
              }
            } catch (error) {
              console.error('Failed to fetch thumbnail:', error);
            }
            return suggestion;
          })
        );
        
        setSuggestions(suggestionsWithImages);
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
    // Trigger parsing after selecting suggestion
    setTimeout(() => handleDreamSubmit(new Event('submit')), 100);
  };

  return (
    <div className="dream-input-container">
      {/* Hero Image */}
      {heroImage && (
        <div className="dream-hero-image">
          <PixabayImage 
            image={heroImage} 
            className="hero"
            showAttribution={true}
          />
        </div>
      )}

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
            '--duration': `${sparkle.duration}ms`
          }}
        />
      ))}

      {/* Magical title with prompt rotation */}
      <div className="dream-title">
        <div className="prompt-text">
          {currentPrompt}
          <div className="prompt-dots">
            <span></span>
            <span></span>
            <span></span>
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
            placeholder="City name: Paris, Tokyo, Barcelona..."
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
                  {suggestion.thumbnail && (
                    <PixabayImage 
                      image={suggestion.thumbnail}
                      className="suggestion-thumbnail"
                      showAttribution={false}
                    />
                  )}
                  <div className="suggestion-content">
                    <span className="suggestion-name">{suggestion.display_name}</span>
                    <span className="suggestion-detail">{suggestion.detail}</span>
                  </div>
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
      </form>

      {/* Processing indicator */}
      {isProcessing && (
        <div className="processing-text">
          <div className="processing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span>Weaving your travel dreams...</span>
        </div>
      )}

      {/* Helper text */}
      <div className="dream-helper">
        ✨ Enter a city name to explore its neighborhoods and attractions
      </div>
    </div>
  );
};

export default DreamInput;
