import { useEffect, useState } from 'react';
import './LocationHero.css';

/**
 * LocationHero Component
 * 
 * A unified visual component for location imagery with responsive design,
 * optimized loading, and accessibility features.
 * 
 * Consolidates: HeroImage functionality
 * 
 * Props:
 * - location: { name, country, state }
 * - images: Array of image URLs or image objects with attribution
 * - imageMeta: Object with photographer and profileUrl for attribution
 * - loading: Boolean
 * - onError: Function to handle image errors
 * - className: Additional CSS classes
 */
const LocationHero = ({ 
    location, 
    images = [], 
    imageMeta,
    loading = false, 
    onError, 
    className = '' 
}) => {
    const [currentImageIndex, setCurrentImageIndex] = useState(0);
    const [imageLoaded, setImageLoaded] = useState(false);
    const [imageError, setImageError] = useState(false);

    // Cycle through images every 8 seconds
    useEffect(() => {
        if (images.length <= 1) return;
        
        const interval = setInterval(() => {
            setCurrentImageIndex(prev => (prev + 1) % images.length);
            setImageLoaded(false);
            setImageError(false);
        }, 8000);

        return () => clearInterval(interval);
    }, [images.length]);

    const handleImageLoad = () => {
        setImageLoaded(true);
        setImageError(false);
    };

    const handleImageError = () => {
        setImageError(true);
        setImageLoaded(false);
        if (onError) onError();
    };

    const currentImage = images[currentImageIndex];
    const locationTitle = location ? `${location.name}${location.country ? `, ${location.country}` : ''}` : '';

    return (
        <div className={`location-hero ${className}`} role="img" aria-label={`Hero image for ${locationTitle}`}>
            {/* Loading Overlay */}
            {loading && (
                <div className="hero-loading-overlay">
                    <div className="hero-loading-spinner"></div>
                    <span className="hero-loading-text">Loading location...</span>
                </div>
            )}

            {/* Image Display */}
            {!loading && (
                <>
                    {currentImage && !imageError ? (
                        <img
                            src={currentImage}
                            alt={locationTitle}
                            className={`hero-image ${imageLoaded ? 'loaded' : 'loading'}`}
                            onLoad={handleImageLoad}
                            onError={handleImageError}
                            loading="lazy"
                        />
                    ) : (
                        <div className="hero-placeholder">
                            <div className="placeholder-icon">📍</div>
                            <div className="placeholder-text">
                                {locationTitle || 'Location Image'}
                            </div>
                        </div>
                    )}

                    {/* Image Counter for Multiple Images */}
                    {images.length > 1 && (
                        <div className="image-counter">
                            <span>{currentImageIndex + 1}</span>
                            <span className="separator">/</span>
                            <span>{images.length}</span>
                        </div>
                    )}

                    {/* Image Attribution */}
                    {imageMeta && (
                        <div className="image-attribution">
                            <a 
                                href={imageMeta.profileUrl || '#'} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="attribution-link"
                            >
                                Photo by {imageMeta.photographer || 'Unknown'}
                            </a>
                        </div>
                    )}
                </>
            )}

            {/* Location Overlay - Removed for clean image display */}
            {/* {location && (
                <div className="location-overlay">
                    <h1 className="location-title">{location.name}</h1>
                    {location.country && (
                        <p className="location-subtitle">
                            {location.state ? `${location.state}, ` : ''}
                            {location.country}
                        </p>
                    )}
                </div>
            )} */}

            {/* Gradient Overlay for text readability - Removed for clean image display */}
            {/* <div className="hero-gradient-overlay"></div> */}
        </div>
    );
};

export default LocationHero;