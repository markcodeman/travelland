import React from 'react';

export default function CustomNeighborhoodSearch({ customQuery, setCustomQuery, city, loading, onSearch }) {
  return (
    <div className="custom-search">
      <label>
        Or search for any neighborhood:
        <input
          type="text"
          value={customQuery}
          onChange={e => setCustomQuery(e.target.value)}
          placeholder="Type a neighborhood..."
        />
      </label>
      <button
        disabled={!customQuery || !city || loading}
        onClick={() => onSearch(customQuery, city)}
      >
        Search
      </button>
    </div>
  );
}
