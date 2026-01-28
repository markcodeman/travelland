import React from 'react';
import './VenueGrid.css';

const VenueGrid = ({ venues, loading, city, intent }) => {

  if (loading) {
    return (
      <div className="venue-grid-loading">
        <div className="venue-grid-skeleton">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="venue-card-skeleton">
              <div className="venue-image-skeleton">
                <div className="skeleton-shimmer"></div>
              </div>
              <div className="venue-content-skeleton">
                <div className="skeleton-line title"></div>
                <div className="skeleton-line subtitle"></div>
                <div className="skeleton-line short"></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!venues || venues.length === 0) {
    return null;
  }

  return (
    <div className="venue-grid-container">
      <div className="venue-grid-header">
        <h2 className="venue-grid-title">Discover {city}</h2>
        {intent && (
          <p className="venue-grid-subtitle">
            Best spots for {intent.split(',').join(' • ')}
          </p>
        )}
      </div>
      
      <div className="venue-grid">
        {venues.map((venue, index) => (
          <div key={venue.id || index} className="venue-card">
            <div className="venue-header">
              <h3 className="venue-name">{venue.name}</h3>
              <div className="venue-badge">
                {venue.category || intent?.split(',')[0] || 'Popular'}
              </div>
            </div>
            
            <div className="venue-content">
              {venue.address && (
                <p className="venue-address">📍 {venue.address}</p>
              )}
              {venue.description && (
                <p className="venue-description">{venue.description}</p>
              )}
              
              <div className="venue-actions">
                {((venue.latitude || venue.lat) && (venue.longitude || venue.lon)) && (
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((venue.latitude || venue.lat) + ',' + (venue.longitude || venue.lon))}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="venue-btn primary"
                  >
                    📍 View on Map
                  </a>
                )}
                {venue.osm_url && (
                  <a
                    href={venue.osm_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="venue-btn secondary"
                  >
                    🗺️ OpenStreetMap
                  </a>
                )}
                <button 
                  className="venue-btn secondary"
                  onClick={() => alert(`Save ${venue.name} to itinerary (feature coming soon!)`)}
                >
                  💖 Save
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      <div className="venue-grid-footer">
        <button className="load-more-btn">
          Load More Places ✨
        </button>
      </div>
    </div>
  );
};

export default VenueGrid;
