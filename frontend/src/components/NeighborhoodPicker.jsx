import React from 'react';
import './NeighborhoodPicker.css';

const NeighborhoodPicker = ({ city, category, neighborhoods, onSelect, onSkip, loading = false }) => {
  if (loading) {
    return (
      <div className="neighborhood-picker-overlay">
        <div className="neighborhood-picker">
          <div className="picker-header">
            <h3>🎯 Finding Best Neighborhoods</h3>
            <p className="picker-subtitle">
              Discovering the perfect spots for {category} in {city}...
            </p>
          </div>
          
          <div className="neighborhoods-loading" style={{ 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center', 
            padding: '40px',
            flexDirection: 'column',
            gap: '16px'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              border: '4px solid #f3f3f3',
              borderTop: '4px solid #667eea',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite'
            }} />
            <p style={{ color: '#666', fontSize: '16px', margin: 0 }}>
              Scanning {city}'s neighborhoods...
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!neighborhoods || neighborhoods.length === 0) {
    return (
      <div className="neighborhood-picker-overlay">
        <div className="neighborhood-picker">
          <div className="picker-header">
            <h3>🎯 Choose Area</h3>
            <p className="picker-subtitle">
              Where in {city} would you like to explore {category}?
            </p>
          </div>
          
          <div style={{ padding: '20px', textAlign: 'center' }}>
            <p style={{ color: '#666', marginBottom: '16px' }}>
              No specific neighborhoods found for {category} in {city}.
            </p>
            <button 
              onClick={() => onSkip && onSkip()}
              style={{
                padding: '12px 24px',
                background: '#667eea',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '16px'
              }}
            >
              Search all of {city} →
            </button>
          </div>
        </div>
      </div>
    );
  }

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
