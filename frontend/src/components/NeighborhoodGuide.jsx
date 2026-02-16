import { useEffect, useState } from 'react';
import { fetchCityHeroImage } from '../services/imageService';
import './NeighborhoodGuide.css';

const NeighborhoodGuide = ({ neighborhood, city, guideData, loading, error, onClose, heroImage }) => {
  const [imgLoading, setImgLoading] = useState(false);

  // Use the heroImage passed from parent component instead of making another API call
  const displayHeroImage = heroImage || 'https://images.unsplash.com/photo-1505060280389-60df856a37e0?auto=format&fit=crop&w=800&q=80';

  if (!neighborhood) return null;

  const getSourceColor = (source) => {
    switch (source) {
      case 'wikipedia': return '#06b6d4';
      case 'seed': return '#8b5cf6';
      case 'geo-enriched': return '#10b981';
      case 'synthesized': return '#f59e0b';
      default: return '#64748b';
    }
  };

  const getConfidenceColor = (confidence) => {
    switch (confidence) {
      case 'high': return '#10b981';
      case 'medium': return '#f59e0b';
      case 'low': return '#ef4444';
      default: return '#64748b';
    }
  };

  return (
    <div className="neighborhood-guide-overlay">
      <div className="neighborhood-guide-modal">
        <div className="guide-hero">
          {imgLoading ? (
            <div className="guide-hero-skeleton animate-pulse" />
          ) : (
            <img 
              src={heroImage || 'https://images.unsplash.com/photo-1505060280389-60df856a37e0?auto=format&fit=crop&w=800&q=80'} 
              alt={neighborhood} 
              className="guide-hero-img"
            />
          )}
          <div className="guide-hero-overlay">
            <div className="guide-header-content">
              <h2 className="guide-nh-name">{neighborhood}</h2>
              <p className="guide-city-name">{city}</p>
            </div>
          </div>
        </div>

        <div className="guide-content">
          {loading ? (
            <div className="guide-loading-state">
              <div className="spinner" />
              <p>Fetching local insights...</p>
            </div>
          ) : error ? (
            <div className="guide-error-state">
              <p>{error}</p>
              <button onClick={onClose} className="guide-close-btn">Close</button>
            </div>
          ) : (
            <>
              <div className="guide-meta">
                {guideData?.source && (
                  <span 
                    className="guide-badge" 
                    style={{ backgroundColor: getSourceColor(guideData.source) }}
                  >
                    Source: {guideData.source}
                  </span>
                )}
                {guideData?.confidence && (
                  <span 
                    className="guide-badge" 
                    style={{ backgroundColor: getConfidenceColor(guideData.confidence) }}
                  >
                    Confidence: {guideData.confidence}
                  </span>
                )}
              </div>

              <div className="guide-text">
                <p>{guideData?.quick_guide}</p>
                {guideData?.source_url && (
                  <a 
                    href={guideData.source_url} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="guide-source-link"
                  >
                    Read more on Wikipedia →
                  </a>
                )}
              </div>

              <div className="guide-actions">
                <button onClick={onClose} className="guide-continue-btn">
                  Continue Exploring
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default NeighborhoodGuide;
