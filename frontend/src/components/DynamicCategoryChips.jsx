import React from 'react';

export default function DynamicCategoryChips({ categories, onSelect, selected, loading }) {
  if (loading) {
    return (
      <div className="suggestion-chips">
        <div className="chips-row">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="suggestion-chip pastel-1 loading">
              <span className="loading-text">...</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!categories || categories.length === 0) {
    return null;
  }

  return (
    <div className="suggestion-chips">
      {categories.length > 0 && (
        <div className="explore-heading">What are you looking for?</div>
      )}
      <div className="chips-row">
        {categories.map(cat => (
          <button
            key={cat.intent}
            className={`suggestion-chip ${selected === cat.intent ? 'selected' : ''}`}
            type="button"
            onClick={() => onSelect && onSelect(cat.intent)}
            aria-label={cat.label}
            title={cat.label}
          >
            <span style={{ marginRight: 8 }}>{cat.icon}</span>
            {cat.label}
          </button>
        ))}
      </div>
    </div>
  );
}
