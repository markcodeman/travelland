import React from 'react';
import './NeighborhoodPicker.css';

const NeighborhoodPicker = ({ city, category, neighborhoods, onSelect, onSkip }) => {
  if (!neighborhoods || neighborhoods.length === 0) return null;

  const getCategoryEmoji = (type) => {
    const emojiMap = {
      'historic': '🏛️',
      'culture': '🎨',
      'nightlife': '🌙',
      'shopping': '🛍️',
      'food': '🍽️',
      'bar': '🍸',
      'pub': '🍺',
      'default': '📍'
    };
    return emojiMap[type] || emojiMap['default'];
  };

  const getCategoryColor = (type) => {
    const colorMap = {
      'historic': '#8B4513',
      'culture': '#9C27B0',
      'nightlife': '#FF6B6B',
      'shopping': '#4CAF50',
      'food': '#FF9800',
      'bar': '#E91E63',
      'pub': '#795548',
      'default': '#667eea'
    };
    return colorMap[type] || colorMap['default'];
  };

  return (
    <div className="neighborhood-picker-overlay">
      <div className="neighborhood-picker">
        <div className="picker-header">
          <h3>🎯 Narrow Down Your Search</h3>
          <p className="picker-subtitle">
            {city} is huge! Pick a neighborhood for better {category} results.
          </p>
        </div>

        <div className="neighborhoods-grid">
          {neighborhoods.map((hood, index) => (
            <button
              key={index}
              className="neighborhood-card"
              onClick={() => onSelect(hood.name)}
              style={{ '--card-color': getCategoryColor(hood.type) }}
            >
              <div className="neighborhood-emoji">
                {getCategoryEmoji(hood.type)}
              </div>
              <div className="neighborhood-info">
                <h4>{hood.name}</h4>
                <p>{hood.description}</p>
              </div>
              <div className="neighborhood-arrow">→</div>
            </button>
          ))}
        </div>

        <div className="picker-footer">
          <button className="skip-button" onClick={onSkip}>
            Search all of {city} anyway →
          </button>
        </div>
      </div>
    </div>
  );
};

export default NeighborhoodPicker;
