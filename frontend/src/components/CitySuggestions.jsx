import React, { useState, useEffect } from 'react';
import './CitySuggestions.css';

const CitySuggestions = ({ city, onCategorySelect }) => {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fallback categories while loading or on error
  const defaultCategories = [
    { icon: '🍽️', label: 'Food & Dining', intent: 'dining' },
    { icon: '🏛️', label: 'Historic Sites', intent: 'historical' },
    { icon: '🎨', label: 'Art & Culture', intent: 'culture' },
    { icon: '🌳', label: 'Parks & Nature', intent: 'nature' },
    { icon: '🛍️', label: 'Shopping', intent: 'shopping' },
    { icon: '🌙', label: 'Nightlife', intent: 'nightlife' }
  ];

  useEffect(() => {
    if (!city) {
      setSuggestions([]);
      return;
    }

    const fetchCategories = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const response = await fetch('/api/city-categories', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ city })
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        console.log('CitySuggestions API response:', data);
        
        if (data.categories && data.categories.length > 0) {
          setSuggestions(data.categories);
        } else {
          console.log('No categories in response, using defaults');
          setSuggestions(defaultCategories);
        }
      } catch (err) {
        console.error('Failed to fetch city categories:', err);
        console.log('Error details:', err.message);
        setError(err.message);
        setSuggestions(defaultCategories);
      } finally {
        setLoading(false);
      }
    };

    fetchCategories();
  }, [city]);

  if (!city || suggestions.length === 0) {
    return null;
  }

  return (
    <div className="city-suggestions">
      <h3 className="suggestions-title">
        ✨ What interests you in {city}?
      </h3>
      {loading && (
        <div className="suggestions-loading" style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
          Discovering what makes {city} special...
        </div>
      )}
      <div className="suggestions-grid">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            className="suggestion-card"
            onClick={() => onCategorySelect(suggestion.intent, suggestion.label)}
            disabled={loading}
          >
            <span className="suggestion-icon">{suggestion.icon}</span>
            <span className="suggestion-label">{suggestion.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default CitySuggestions;
