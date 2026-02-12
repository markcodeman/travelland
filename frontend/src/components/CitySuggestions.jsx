import './CitySuggestions.css';

const CitySuggestions = ({ city, neighborhood, onCategorySelect, searchResults }) => {
  console.log('CitySuggestions DEBUG:', { 
    city, 
    neighborhood,
    searchResults,
    hasCategories: searchResults?.categories?.length > 0,
    categoriesLength: searchResults?.categories?.length,
    firstCategory: searchResults?.categories?.[0]
  });
  
  // Map categories from backend into usable suggestions
  const suggestions = (searchResults?.categories || [])
    .map((c) => {
      if (!c) return null;
      if (typeof c === 'string') {
        return {
          label: c,
          intent: c.toLowerCase(),
          icon: '📍',
        };
      }
      const label = c.label || c.category || c.name || '';
      if (!label) return null;
      return {
        label,
        intent: c.intent || label.toLowerCase(),
        icon: c.icon || '📍',
      };
    })
    .filter(Boolean);
  
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
    <div className="city-suggestions">
      <h3 className="suggestions-title">
        ✨ What interests you in {getLocationText()}?
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
