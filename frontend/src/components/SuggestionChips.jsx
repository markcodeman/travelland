import React from 'react';

const baseSuggestions = [
  { id: 'transport', label: 'Public transport', icon: '🚌', cls: 'pastel-2' },
  { id: 'markets', label: 'Local markets', icon: '🛒', cls: 'pastel-3' },
  { id: 'family', label: 'Family friendly', icon: '👨‍👩‍👧', cls: 'pastel-4' },
  { id: 'events', label: 'Popular events', icon: '🎪', cls: 'pastel-5' },
  { id: 'hidden', label: 'Hidden gems', icon: '💎', cls: 'pastel-6' },
  { id: 'coffee', label: 'Coffee & tea', icon: '☕', cls: 'pastel-1' },
  { id: 'parks', label: 'Parks & nature', icon: '🌳', cls: 'pastel-7' },
];

const rioSuggestions = [
  { id: 'tourist', label: 'Tourist Hotspots', icon: '📍', cls: 'rio-1' },
  { id: 'local', label: 'Local Vibes', icon: '🌶️', cls: 'rio-2' },
  { id: 'foodie', label: 'Foodie Areas', icon: '🍲', cls: 'rio-3' },
  { id: 'nightlife', label: 'Nightlife', icon: '🎶', cls: 'rio-4' },
  { id: 'budget', label: 'Budget-Friendly', icon: '💸', cls: 'rio-5' },
];

export default function SuggestionChips({ onSelect, city }) {
  const normalized = (city || '').toLowerCase();
  const showRio = normalized.includes('rio');
  const list = showRio ? rioSuggestions.concat(baseSuggestions) : baseSuggestions;

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
