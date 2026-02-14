import React from 'react';
import './NeighborhoodGuide.css';

const NeighborhoodGuide = ({ neighborhood, city, guideData, loading, error, onClose }) => {
  if (!neighborhood) return null;

  return (
    <div className="neighborhood-guide-overlay">
      <div className="neighborhood-guide">
        <div className="guide-header">
          <h2>🗺️ {neighborhood}</h2>
          <button className="guide-close" onClick={onClose} aria-label="Close guide">
            ✕
          </button>
        </div>

        {loading && (
          <div className="guide-loading">
            <div className="spinner" />
            <p>Loading neighborhood guide...</p>
          </div>
        )}

        {error && (
          <div className="guide-error">
            <p>⚠️ Unable to load guide for {neighborhood}</p>
            <p className="error-detail">{error}</p>
          </div>
        )}

        {!loading && !error && guideData && (
          <div className="guide-content">
            <div className="guide-text">
              {guideData.quick_guide}
            </div>

            {guideData.source_url && (
              <div className="guide-source">
                <a 
                  href={guideData.source_url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="source-link"
                >
                  📚 Read more
                </a>
              </div>
            )}

            <div className="guide-meta">
              <span className="confidence-badge" data-confidence={guideData.confidence || 'medium'}>
                {guideData.source === 'wikipedia' && '📖 Wikipedia'}
                {guideData.source === 'ddgs' && '🔍 Web Search'}
                {guideData.source === 'synthesized' && '✨ Synthesized'}
                {guideData.source === 'geo-enriched' && '🌍 Geo Data'}
                {!guideData.source && '📍 Local Info'}
              </span>
            </div>
          </div>
        )}

        <div className="guide-footer">
          <button className="guide-action-btn" onClick={onClose}>
            Continue Exploring
          </button>
        </div>
      </div>
    </div>
  );
};

export default NeighborhoodGuide;
