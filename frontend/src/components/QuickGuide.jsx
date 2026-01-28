import React, { useEffect } from 'react';
import { triggerUnsplashDownload } from '../services/imageService';

export default function QuickGuide({ guide, images, source, source_url, cityImage, cityImageMeta }) {
  if (!guide) return null;

  // Trigger Unsplash download event when city image is displayed
  React.useEffect(() => {
    if (cityImage && cityImage !== 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=80') {
      triggerUnsplashDownload(cityImage);
    }
  }, [cityImage]);

  return (
    <div className="quick-guide">
      {cityImage && (
        <div className="quick-guide-hero">
          <img src={cityImage} alt={`${guide.split(' ').slice(0, 3).join(' ')}...`} style={{ width: '100%', height: 'auto', borderRadius: '8px', marginBottom: '8px' }} />
          <div className="quick-guide-attribution">
            <small>Photo by <a href={cityImageMeta.profileUrl || 'https://unsplash.com'} target="_blank" rel="noopener noreferrer">{cityImageMeta.photographer || 'Unsplash'}</a> on <a href="https://unsplash.com" target="_blank" rel="noopener noreferrer">Unsplash</a></small>
          </div>
        </div>
      )}
      <h2>Quick guide</h2>
      <p>{guide}</p>
      {Array.isArray(images) && images.length > 0 && (
        <div className="quick-guide-images">
          {images.slice(0, 8).map((img, i) => (
            <figure key={`${img.id || i}`} className="quick-thumb">
              <a href={img.source_url || img.url} target="_blank" rel="noreferrer">
                <img src={img.url} alt={img.attribution || `Image ${i + 1}`} loading="lazy" style={{ maxWidth: '300px', height: 'auto' }} />
              </a>
              {img.attribution && (
                <figcaption className="quick-thumb-attribution">{img.attribution}</figcaption>
              )}
            </figure>
          ))}
        </div>
      )}
      {source && (
        <div className="quick-source">Source: {source}{source_url ? (<a href={source_url} target="_blank" rel="noreferrer"> ↗</a>) : null}</div>
      )}
    </div>
  );
}
