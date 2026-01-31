import React, { useEffect } from 'react';
import './HeroImage.css';
import { triggerUnsplashDownload } from '../services/imageService';

const DEFAULT_HERO = 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=80';

const HeroImage = ({ city, intent, loading, heroImage, heroImageMeta }) => {
  if (!city && !loading) return null;

  const imageUrl = heroImage || DEFAULT_HERO;

  // Trigger Unsplash download event when image is displayed
  useEffect(() => {
    if (imageUrl && imageUrl !== DEFAULT_HERO) {
      triggerUnsplashDownload(imageUrl);
    }
  }, [imageUrl]);

  const getAltText = (cityName, userIntent) => {
    if (userIntent) {
      return `${cityName} • ${userIntent}`;
    }
    return `Stunning views of ${cityName}`;
  };

  return (
    <div className="hero-image-container">
      {loading ? (
        <div className="hero-loading">
          <div className="hero-skeleton">
            <div className="skeleton-shimmer"></div>
          </div>
        </div>
      ) : (
        <>
          <div className="hero-image-wrapper">
            <img
              src={imageUrl}
              alt={getAltText(city, intent)}
              className="hero-image"
              onError={(e) => {
                // Fallback to cityscape if specific intent image fails
                if (!e.target.src.includes('cityscape')) {
                  e.target.src = `https://source.unsplash.com/1200x600/?${city.toLowerCase().replace(/\s+/g, '-')},cityscape&auto=format&fit=crop`;
                }
              }}
            />
            <div className="hero-overlay">
              <div className="hero-content">
                <h1 className="hero-title">{city}</h1>
                {intent && (
                  <p className="hero-subtitle">
                    Discover {intent.split(',').join(' • ')}
                  </p>
                )}
                <div className="hero-attribution">
                  <small>Photo by <a href={heroImageMeta.profileUrl ? `${heroImageMeta.profileUrl}?utm_source=travelland&utm_medium=referral` : 'https://unsplash.com'} target="_blank" rel="noopener noreferrer">{heroImageMeta.photographer || 'Unsplash'}</a> on <a href="https://unsplash.com?utm_source=travelland&utm_medium=referral" target="_blank" rel="noopener noreferrer">Unsplash</a></small>
                </div>
              </div>
            </div>
          </div>
          
          {/* Floating action buttons */}
          <div className="hero-actions">
            <button className="hero-action-btn primary">
              📍 Explore Map
            </button>
            <button className="hero-action-btn secondary">
              📸 View Gallery
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default HeroImage;
