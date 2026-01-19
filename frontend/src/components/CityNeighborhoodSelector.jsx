import React from 'react';

export default function CityNeighborhoodSelector({ city, setCity, neighborhood, setNeighborhood, cityNeighborhoods }) {
  return (
    <div className="selector-group">
      <label>
        City:
        <select value={city} onChange={e => { setCity(e.target.value); setNeighborhood(''); }}>
          <option value="">Select a city</option>
          {Object.keys(cityNeighborhoods).map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </label>
      {city && (
        <label>
          Neighborhood:
          <select value={neighborhood} onChange={e => setNeighborhood(e.target.value)}>
            <option value="">Select a neighborhood</option>
            {cityNeighborhoods[city].map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
