import React from 'react';

export default function QuickGuide({ guide, images, source, source_url }) {
  if (!guide) return null;
  return (
    <div className="quick-guide">
      <h2>Quick guide</h2>
      <p>{guide}</p>
      {images && images.length > 0 && (
        <div className="quick-guide-images">
          {images.slice(0, 8).map((img, i) => (
            <figure key={`${img.id || i}`} className="quick-thumb">
              <a href={img.source_url || img.url} target="_blank" rel="noreferrer">
                <img src={img.url} alt={img.attribution || `Image ${i + 1}`} loading="lazy" />
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
