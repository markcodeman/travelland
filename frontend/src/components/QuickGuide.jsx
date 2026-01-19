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
            <a key={`${img.id || i}`} href={img.url} target="_blank" rel="noreferrer" className="quick-thumb">
              <img src={img.url} alt={`Image ${i + 1}`} loading="lazy" />
            </a>
          ))}
        </div>
      )}
      {source && (
        <div className="quick-source">Source: {source}{source_url ? (<a href={source_url} target="_blank" rel="noreferrer"> ↗</a>) : null}</div>
      )}
    </div>
  );
}
