import React from 'react';

const baseSuggestions = [
  { id: 'transport', label: 'Public transport', icon: '🚌', cls: 'pastel-2' },
  { id: 'hidden', label: 'Hidden gems', icon: '💎', cls: 'pastel-6' },
  { id: 'coffee', label: 'Coffee & tea', icon: '☕', cls: 'pastel-1' },
];

const rioSuggestions = [
  // Removed tourist, local, budget to reduce clutter
];

export default function SuggestionChips({ onSelect, city }) {
  const list = rioSuggestions.concat(baseSuggestions);

  return (
    <div className="suggestion-chips">
      {city ? (
        <div className="explore-heading">{`Explore ${city}`}</div>
      ) : (
        <label>What are you looking for?</label>
      )}
      <div className="chips-row">
        {list.map(s => (
          <button
            key={s.id}
            className={`suggestion-chip ${s.cls}`}
            type="button"
            onClick={() => onSelect && onSelect(s.id)}
            aria-label={s.label}
          >
            <span className="chip-icon">{s.icon}</span>
            <span className="chip-label">{s.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
