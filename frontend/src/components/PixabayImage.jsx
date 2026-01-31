import React from 'react';
import './PixabayImage.css';

const PixabayImage = ({ image, className = "", showAttribution = true, onClick }) => {
  if (!image) return null;

  const handleImageClick = () => {
    if (onClick) {
      onClick();
    } else if (image.pageURL) {
      // Open Pixabay page in new tab
      window.open(image.pageURL, '_blank', 'noopener,noreferrer');
    }
  };

  const attributionText = `Photo by ${image.user || 'Unknown'} on Pixabay`;

  return (
    <div className={`pixabay-image-container ${className}`}>
      <img
        src={image.webformatURL || image.previewURL}
        alt={image.tags || `Image by ${image.user || 'Unknown'} on Pixabay`}
        className="pixabay-image"
        onClick={handleImageClick}
        loading="lazy"
      />
      
      {showAttribution && (
        <div className="pixabay-attribution">
          <a 
            href={image.pageURL}
            target="_blank"
            rel="noopener noreferrer"
            className="attribution-link"
            title="View on Pixabay"
          >
            {attributionText}
          </a>
        </div>
      )}
    </div>
  );
};

export default PixabayImage;
