import React, { useEffect } from 'react';
import './VenueGrid.css';
import { triggerUnsplashDownload } from '../services/imageService';

const DEFAULT_VENUE_IMAGE = 'https://images.unsplash.com/photo-1445019980597-93fa8acb246c?auto=format&fit=crop&w=800&q=80';

const VenueGrid = ({ venues, loading, city, intent, imageUrls = [], imageMetas = [] }) => {
  // Trigger Unsplash download events when images are displayed
  useEffect(() => {
    imageUrls.forEach((url) => {
      if (url && url !== DEFAULT_VENUE_IMAGE) {
        triggerUnsplashDownload(url);
      }
    });
  }, [imageUrls]);

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
            <div className="venue-image-container">
              <img
                src={imageUrls[index] || DEFAULT_VENUE_IMAGE}
                alt={venue.name}
                className="venue-image"
                onError={(e) => {
                  e.target.src = DEFAULT_VENUE_IMAGE;
                }}
              />
              <div className="venue-badge">
                {venue.category || intent?.split(',')[0] || 'Popular'}
              </div>
              <div className="venue-attribution">
                <small>Photo by <a href={imageMetas[index]?.profileUrl || 'https://unsplash.com'} target="_blank" rel="noopener noreferrer">{imageMetas[index]?.photographer || 'Unsplash'}</a> on <a href="https://unsplash.com" target="_blank" rel="noopener noreferrer">Unsplash</a></small>
              </div>
            </div>
            
            <div className="venue-content">
              <h3 className="venue-name">{venue.name}</h3>
              {venue.address && (
                <p className="venue-address">📍 {venue.address}</p>
              )}
              {venue.description && (
                <p className="venue-description">{venue.description}</p>
              )}
              
              <div className="venue-actions">
                <button className="venue-btn primary">
                  View Details
                </button>
                <button className="venue-btn secondary">
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
