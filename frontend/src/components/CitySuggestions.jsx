import React from 'react';
import './CitySuggestions.css';

const CitySuggestions = ({ city, onCategorySelect, searchResults }) => {
  console.log('CitySuggestions DEBUG:', { 
    city, 
    searchResults,
    hasCategories: searchResults?.categories?.length > 0,
    categoriesLength: searchResults?.categories?.length,
    firstCategory: searchResults?.categories?.[0]
  });
  
  // Only use categories from search results - no generic fallbacks
  const suggestions = searchResults?.categories || [];
  
  // Don't show anything if no real categories exist
  if (!city || suggestions.length === 0) {
    return null;
  }

  return (
    <div className="city-suggestions">
      <h3 className="suggestions-title">
        ✨ What interests you in {city}?
      </h3>
      <div className="suggestions-grid">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            className="suggestion-card"
            onClick={() => onCategorySelect(suggestion.intent, suggestion.label)}
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
