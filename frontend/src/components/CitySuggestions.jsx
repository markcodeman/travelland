const CitySuggestions = ({ city, neighborhood, onCategorySelect, searchResults }) => {
  const categories = Array.isArray(searchResults?.categories) ? searchResults.categories : [];
  console.log('CitySuggestions DEBUG:', { 
    city, 
    neighborhood,
    searchResults,
    hasCategories: categories.length > 0,
    categoriesLength: categories.length,
    firstCategory: categories[0]
  });
  
  const pickIcon = (label) => {
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
  };

  // Map categories from backend into usable suggestions
  const suggestions = categories
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

export default CitySuggestions;
