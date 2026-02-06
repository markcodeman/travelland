import React from 'react';

export default function QuickGuide({ guide, images, source, source_url }) {
  if (!guide) return null;
  
  return (
    <div className="quick-guide">
      <div className="quick-guide-content">
        {guide}
      </div>
      {source && (
        <div className="quick-source">
          Source: {source_url ? (
            <a href={source_url} target="_blank" rel="noopener noreferrer">{source}</a>
          ) : source}
        </div>
      )}
      {images && images.length > 0 && (
        <div className="quick-images">
          {images.map((img, i) => (
            <img key={i} src={img.url || img} alt="" className="quick-image" />
          ))}
        </div>
      )}
    </div>
  );
}
