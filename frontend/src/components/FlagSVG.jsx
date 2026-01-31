import React from 'react';

const FlagSVG = ({ country, size = 24 }) => {
  const flags = {
    'France': '🇫🇷',
    'Japan': '🇯🇵',
    'Spain': '🇪🇸',
    'United States': '🇺🇸',
    'United Kingdom': '🇬🇧',
    'Italy': '🇮🇹',
    'Australia': '🇦🇺',
    'China': '🇨🇳',
    'Netherlands': '🇳🇱',
    'Germany': '🇩🇪',
    'Portugal': '🇵🇹',
    'United Arab Emirates': '🇦🇪',
    'Singapore': '🇸🇬',
    'Hong Kong': '🇭🇰',
    'India': '🇮🇳',
    'Canada': '🇨🇦',
    'Belgium': '🇧🇪',
    'Austria': '🇦🇹',
    'Morocco': '🇲🇦',
    'Montenegro': '🇲🇪',
    'Czech Republic': '🇨🇿',
    'Norway': '🇳🇴',
    'Mexico': '🇲🇽'
  };

  const emoji = flags[country] || '🏳️';
  
  return (
    <span 
      className="flag-svg"
      style={{ 
        fontSize: `${size}px`,
        display: 'inline-block',
        width: `${size}px`,
        height: `${size}px`,
        lineHeight: 1,
        textAlign: 'center',
        backgroundImage: `url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><text y="24" font-size="24">${emoji}</text></svg>')`,
        backgroundSize: 'contain',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center'
      }}
    >
      {emoji}
    </span>
  );
};

export default FlagSVG;
