import { useCallback, useMemo, useState } from 'react';
import { useDebounce, useLocalStorage, useModal } from '../utils/componentUtils';
import {
    ContentSection,
    LocationHero
} from './index';
import './LocationGuide.css';

// Utility function to encode neighborhood text
const encodeNeighborhoodText = (text) => {
    return text
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, '') // Remove special characters
        .replace(/\s+/g, '-') // Replace spaces with hyphens
        .trim();
};

/**
 * LocationGuide Component
 * 
 * Consolidates NeighborhoodGuide, SearchResults, CitySuggestions, and NeighborhoodPicker
 * into a single, unified location display component.
 * 
 * Features:
 * - Dynamic content switching based on context
 * - Integrated search and suggestions
 * - Modal-based neighborhood selection
 * - Persistent state management
 * - Responsive design
 * 
 * Props:
 * - location: LocationWithCoords
 * - neighborhoods: Neighborhood[]
 * - images: ImageSource[]
 * - imageMeta: Object with photographer and profileUrl
 * - sections: ContentSection[]
 * - showNeighborhoodPicker: boolean
 * - showSearch: boolean
 * - showSuggestions: boolean
 * - onLocationSelect: Function
 * - onNeighborhoodSelect: Function
 * - onSearch: Function
 */

const LocationGuide = ({
    location,
    neighborhoods = [],
    images = [],
    imageMeta,
    sections = [],
    showNeighborhoodPicker = true,
    showSearch = true,
    showSuggestions = true,
    onLocationSelect,
    onNeighborhoodSelect,
    onSearch,
    className = ''
}) => {
    // State management
    const [searchQuery, setSearchQuery] = useState('');
    const [recentLocations, setRecentLocations] = useLocalStorage('recent_locations', []);
    const [favoriteLocations, setFavoriteLocations] = useLocalStorage('favorite_locations', []);
    
    // Modal states
    const neighborhoodModal = useModal(false);
    const searchModal = useModal(false);
    
    // Search functionality
    const debouncedSearch = useDebounce((query) => {
        if (onSearch && query.trim()) {
            onSearch(query);
        }
    }, 300);

// Content generation based on context
    const generateContentSections = useCallback(() => {
        const contentSections = [];

        // Location-specific content
        if (location) {
            // Add fun fact from backend if available
            if (location.funFact) {
                contentSections.push({
                    type: 'fun_fact',
                    title: 'Did You Know?',
                    content: location.funFact,
                    icon: '💡'
                });
            } else if (!(sections && sections.some(s => s.type === 'fun_fact'))) {
                // Only add a default fun_fact if the parent didn't already provide one
                contentSections.push({
                    type: 'fun_fact',
                    title: 'Did You Know?',
                    content: `Discover amazing facts about ${location.name}!`,
                    icon: '💡'
                });
            }

            if (neighborhoods.length > 0) {
                contentSections.push({
                    type: 'city_suggestions',
                    title: 'Explore Neighborhoods',
                    content: (
                        <div className="neighborhoods-grid">
                            {neighborhoods.slice(0, 6).map((hood, index) => (
                                <button
                                    key={index}
                                    className="neighborhood-card"
                                    onClick={() => handleNeighborhoodSelect(hood)}
                                    aria-label={`Explore ${hood.name}`}
                                >
                                    <div className="neighborhood-name">{hood.name}</div>
                                    {hood.description && (
                                        <div className="neighborhood-desc">{hood.description}</div>
                                    )}
                                </button>
                            ))}
                        </div>
                    )
                });
            }
        }

        // Custom sections from props
        contentSections.push(...sections);

        return contentSections;
    }, [location, neighborhoods, sections]);

    // Memoize content sections to prevent infinite re-renders
    const contentSections = useMemo(() => generateContentSections(), [generateContentSections]);

    // Handle search input changes
    const handleSearchChange = useCallback((value) => {
        setSearchQuery(value);
        debouncedSearch(value);
    }, [debouncedSearch]);

    // Handle location selection
    const handleLocationSelect = useCallback((newLocation) => {
        // Add to recent locations
        const newRecent = [newLocation, ...recentLocations.filter(loc => 
            loc.name !== newLocation.name
        )].slice(0, 10);
        setRecentLocations(newRecent);
        
        // Update selected location
        setSelectedNeighborhood(null);
        setSearchQuery('');
        
        if (onLocationSelect) {
            onLocationSelect(newLocation);
        }
    }, [recentLocations, setRecentLocations, onLocationSelect]);

    // Handle neighborhood selection
    const handleNeighborhoodSelect = useCallback((neighborhood) => {
        if (onNeighborhoodSelect) {
            // Encode neighborhood text before passing
            const encodedNeighborhood = {
                ...neighborhood,
                encodedName: encodeNeighborhoodText(neighborhood.name)
            };
            onNeighborhoodSelect(encodedNeighborhood);
        }
    }, [onNeighborhoodSelect]);

    // Handle favorite toggle
    const toggleFavorite = useCallback((loc) => {
        const isFavorite = favoriteLocations.some(fav => fav.name === loc.name);
        const newFavorites = isFavorite 
            ? favoriteLocations.filter(fav => fav.name !== loc.name)
            : [loc, ...favoriteLocations];
        setFavoriteLocations(newFavorites);
    }, [favoriteLocations, setFavoriteLocations]);

    // Render recent locations
    const renderRecentLocations = () => (
        <div className="recent-locations">
            <h3>Recent Locations</h3>
            <div className="location-list">
                {recentLocations.map((loc, index) => (
                    <button
                        key={index}
                        className="location-item"
                        onClick={() => handleLocationSelect(loc)}
                        aria-label={`Go to ${loc.name}`}
                    >
                        <span className="location-name">{loc.name}</span>
                        <span className="location-country">{loc.country}</span>
                        <button
                            className="favorite-btn"
                            onClick={(e) => {
                                e.stopPropagation();
                                toggleFavorite(loc);
                            }}
                            aria-label={favoriteLocations.some(fav => fav.name === loc.name) ? "Remove from favorites" : "Add to favorites"}
                        >
                            {favoriteLocations.some(fav => fav.name === loc.name) ? '★' : '☆'}
                        </button>
                    </button>
                ))}
            </div>
        </div>
    );

    // Render favorite locations
    const renderFavoriteLocations = () => (
        <div className="favorite-locations">
            <h3>Favorites</h3>
            <div className="location-list">
                {favoriteLocations.map((loc, index) => (
                    <button
                        key={index}
                        className="location-item favorite"
                        onClick={() => handleLocationSelect(loc)}
                        aria-label={`Go to ${loc.name}`}
                    >
                        <span className="location-name">{loc.name}</span>
                        <span className="location-country">{loc.country}</span>
                        <button
                            className="favorite-btn"
                            onClick={(e) => {
                                e.stopPropagation();
                                toggleFavorite(loc);
                            }}
                            aria-label="Remove from favorites"
                        >
                            ★
                        </button>
                    </button>
                ))}
            </div>
        </div>
    );

    // Render search suggestions
    const renderSearchSuggestions = () => (
        <div className="search-suggestions">
            <h3>Popular Searches</h3>
            <div className="suggestion-tags">
                {['Coffee shops', 'Restaurants', 'Museums', 'Parks', 'Shopping'].map((suggestion, index) => (
                    <button
                        key={index}
                        className="suggestion-tag"
                        onClick={() => handleSearchChange(suggestion)}
                    >
                        {suggestion}
                    </button>
                ))}
            </div>
        </div>
    );

    return (
        <div className={`location-guide ${className}`}>
            {/* Header Section */}
            <div className="guide-header">
                {location && (
                    <LocationHero
                        location={location}
                        images={images}
                        imageMeta={imageMeta}
                        className="guide-hero"
                    />
                )}
                
                {/* Action Buttons - Removed for clean display */}
                {/* <div className="guide-actions">
                    {showSearch && (
                        <button
                            className="action-btn search-btn"
                            onClick={searchModal.openModal}
                            aria-label="Open search"
                        >
                            🔍 Search
                        </button>
                    )}
                    
                    {showNeighborhoodPicker && neighborhoods.length > 0 && (
                        <button
                            className="action-btn neighborhood-btn"
                            onClick={neighborhoodModal.openModal}
                            aria-label="Explore neighborhoods"
                        >
                            🏘️ Neighborhoods
                        </button>
                    )}
                    
                    {showSuggestions && (
                        <button
                            className="action-btn suggestions-btn"
                            onClick={() => {
                                // Toggle suggestions section
                            }}
                            aria-label="View suggestions"
                        >
                            💡 Suggestions
                        </button>
                    )}
                </div> */}
            </div>

            {/* Content Sections */}
            <div className="guide-content">
                {contentSections.length > 0 ? (
                    <ContentSection
                        sections={contentSections}
                        layout="vertical"
                        spacing="medium"
                    />
                ) : (
                    <div className="empty-state">
                        <div className="empty-icon">📍</div>
                        <h3>Explore {location ? location.name : 'Your Destination'}</h3>
                        <p>Start by searching for places or exploring neighborhoods to discover amazing spots!</p>
                    </div>
                )}
            </div>

            {/* Sidebar with Additional Features */}
            <div className="guide-sidebar">
                {showSuggestions && renderSearchSuggestions()}
                {recentLocations.length > 0 && renderRecentLocations()}
                {favoriteLocations.length > 0 && renderFavoriteLocations()}
            </div>

            {/* Neighborhood Modal */}
            {showNeighborhoodPicker && (
                <div className={`modal-overlay ${neighborhoodModal.open ? 'open' : ''}`}>
                    <div className="modal-content">
                        <div className="modal-header">
                            <h3>Explore {location?.name || 'Neighborhoods'}</h3>
                            <button 
                                className="modal-close"
                                onClick={neighborhoodModal.closeModal}
                                aria-label="Close modal"
                            >
                                ✕
                            </button>
                        </div>
                        <div className="modal-body">
                            <div className="neighborhoods-list">
                                {neighborhoods.map((hood, index) => (
                                    <div
                                        key={index}
                                        className="neighborhood-item"
                                        onClick={() => handleNeighborhoodSelect(hood)}
                                    >
                                        <div className="neighborhood-info">
                                            <h4>{hood.name}</h4>
                                            {hood.description && <p>{hood.description}</p>}
                                            {hood.encodedName && (
                                                <small className="encoded-name">{hood.encodedName}</small>
                                            )}
                                        </div>
                                        <button className="explore-btn">Explore</button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Search Modal */}
            {showSearch && (
                <div className={`modal-overlay ${searchModal.open ? 'open' : ''}`}>
                    <div className="modal-content search-modal">
                        <div className="modal-header">
                            <h3>Search {location?.name || 'Locations'}</h3>
                            <button 
                                className="modal-close"
                                onClick={searchModal.closeModal}
                                aria-label="Close modal"
                            >
                                ✕
                            </button>
                        </div>
                        <div className="modal-body">
                            <input
                                type="text"
                                value={searchQuery}
                                placeholder="Search for places, attractions, or activities..."
                                onChange={(e) => handleSearchChange(e.target.value)}
                                className="search-input"
                                autoFocus
                            />
                            {renderSearchSuggestions()}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default LocationGuide;