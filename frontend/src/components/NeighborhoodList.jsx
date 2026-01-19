import React, { useState } from 'react';

export default function NeighborhoodList({ options = [], value, onSelect }) {
  const [expanded, setExpanded] = useState(false);

  if (!options || options.length === 0) return null;

  const preview = expanded ? options : options.slice(0, 6);

  return (
    <div className="neighborhood-list">
      <label>Popular neighborhoods:</label>
      <div className="neighborhood-buttons">
        {preview.map(n => (
          <button
            key={n}
            className={`neighborhood-btn ${value === n ? 'active' : ''}`}
            onClick={() => onSelect(n)}
            type="button"
          >
            {n}
          </button>
        ))}
        {options.length > 6 && (
          <button className="neighborhood-more" onClick={() => setExpanded(!expanded)} type="button">
            {expanded ? 'Show less' : `+${options.length - 6} more`}
          </button>
        )}
      </div>
    </div>
  );
}
