import React from 'react';
import './VenueCard.css';

export default function VenueCard({ venue, onDirections, onMap, onSave }) {
  return (
    <div className="venue-card">
      <div className="venue-card-header">
        <span className="venue-emoji">{venue.emoji || '📍'}</span>
        <span className="venue-name">{venue.name}</span>
      </div>
      {venue.image && (
        <img className="venue-image" src={venue.image} alt={venue.name} />
      )}
      <div className="venue-details">
        {venue.address && <div className="venue-address">{venue.address}</div>}
        {venue.description && <div className="venue-desc">{venue.description}</div>}
      </div>
      <div className="venue-actions">
        {venue.mapsUrl && (
          <a href={venue.mapsUrl} target="_blank" rel="noopener noreferrer" className="venue-btn">Google Maps</a>
        )}
        {onDirections && (
          <button className="venue-btn" onClick={() => onDirections(venue)}>Directions</button>
        )}
        {onMap && (
          <button className="venue-btn" onClick={() => onMap(venue)}>Show on Map</button>
        )}
        {onSave && (
          <button className="venue-btn" onClick={() => onSave(venue)}>Save</button>
        )}
      </div>
    </div>
  );
}
