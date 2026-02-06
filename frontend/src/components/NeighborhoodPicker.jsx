import React from 'react';
import './NeighborhoodPicker.css';
import { pinyin } from 'pinyin-pro';

const NeighborhoodPicker = ({ city, category, neighborhoods, onSelect, onSkip, loading = false }) => {
  // Override translations for better names (pinyin is fallback)
  const chineseTranslations = {
    // Shanghai landmarks with better English names
    '外滩': 'The Bund',
    '南京路': 'Nanjing Road',
    '陆家嘴': 'Lujiazui',
    '豫园': 'Yu Garden',
    '静安寺': "Jing'an Temple",
    '新天地': 'Xintiandi',
    '田子坊': 'Tianzifang',
    '浦东': 'Pudong',
    '浦西': 'Puxi',
    // Common district suffixes
    '街道': 'District',
    '区': 'District',
    '镇': 'Town',
    '乡': 'Township',
    '村': 'Village',
  };

  const formatBilingualName = (name) => {
    // Check if name contains Chinese characters
    const hasChinese = /[\u4e00-\u9fff]/.test(name);
    const hasKorean = /[가-힣]/.test(name);
    
    if (hasChinese) {
      // First apply specific translations for landmarks
      let displayName = name;
      for (const [cn, en] of Object.entries(chineseTranslations)) {
        if (name.includes(cn)) {
          displayName = displayName.replace(cn, `${cn} (${en})`);
        }
      }
      
      // If no specific translation was applied, convert to pinyin
      if (displayName === name) {
        const pinyinName = pinyin(name, { toneType: 'none', type: 'string', separator: ' ' });
        // Capitalize each word
        const capitalized = pinyinName.replace(/\b\w/g, c => c.toUpperCase());
        displayName = `${name} (${capitalized})`;
      }
      
      return displayName;
    } else if (hasKorean) {
      // If it's Korean, try to extract English part if available, or just show Korean
      const englishMatch = name.match(/\(([^)]+)\)/);
      if (englishMatch) {
        // Format: Korean (English)
        const koreanPart = name.replace(/\s*\([^)]+\)/, '').trim();
        return `${koreanPart} (${englishMatch[1]})`;
      }
      // Just Korean, no English part available
      return name;
    } else {
      // If it's English, we could add Korean if we had a mapping
      // For now, just return as-is
      return name;
    }
  };

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

  const getCategoryEmoji = (type, name) => {
    const emojiMap = {
      'historic': '🏛️',
      'culture': '🎨',
      'nightlife': '🌙',
      'shopping': '🛍️',
      'food': '🍽️',
      'bar': '🍸',
      'pub': '🍺',
      'residential': '🏘️',
      'nature': '🌳',
      'beach': '🏖️',
      'waterfront': '🌊',
      'market': '🛒',
      'default': '📍'
    };
    
    // Check for specific neighborhood names
    const lowerName = (name || '').toLowerCase();
    if (lowerName.includes('beach') || lowerName.includes('coastal') || lowerName.includes('waterfront')) {
      return '🏖️';
    }
    if (lowerName.includes('park') || lowerName.includes('garden') || lowerName.includes('nature')) {
      return '🌳';
    }
    if (lowerName.includes('historic') || lowerName.includes('old town')) {
      return '🏛️';
    }
    if (lowerName.includes('market') || lowerName.includes('shopping')) {
      return '🛍️';
    }
    if (lowerName.includes('wine') || lowerName.includes('vineyard')) {
      return '🍷';
    }
    
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
      'residential': '#4CAF50',
      'nature': '#2E7D32',
      'beach': '#FF9800',
      'waterfront': '#03A9F4',
      'market': '#8BC34A',
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
                {getCategoryEmoji(hood.type, hood.name)}
              </div>
              <div className="neighborhood-info">
                <h4>{formatBilingualName(hood.name)}</h4>
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
