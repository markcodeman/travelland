// Location-related JavaScript types and utilities
// Using JSDoc for type annotations

/**
 * @typedef {Object} Location
 * @property {string} name - The name of the location
 * @property {string} [country] - The country name
 * @property {string} [state] - The state name
 * @property {string} [countryCode] - The country code
 * @property {string} [stateCode] - The state code
 */

/**
 * @typedef {Object} LocationWithCoords
 * @property {string} name - The name of the location
 * @property {string} [country] - The country name
 * @property {string} [state] - The state name
 * @property {string} [countryCode] - The country code
 * @property {string} [stateCode] - The state code
 * @property {number} [lat] - Latitude coordinate
 * @property {number} [lon] - Longitude coordinate
 */

/**
 * @typedef {Object} Neighborhood
 * @property {string} name - The neighborhood name
 * @property {string} [description] - Description of the neighborhood
 * @property {string} [image] - Image URL for the neighborhood
 * @property {string} [category] - Category of the neighborhood
 * @property {number} [population] - Population of the neighborhood
 * @property {string[]} [attractions] - List of attractions
 */

/**
 * @typedef {Object} ImageSource
 * @property {string} url - The image URL
 * @property {string} [alt] - Alternative text for accessibility
 * @property {string} [credit] - Image credit information
 * @property {number} [width] - Image width
 * @property {number} [height] - Image height
 * @property {string} [type] - Image type (hero, thumbnail, placeholder)
 */

/**
 * @typedef {'fun_fact'|'neighborhood_info'|'search_results'|'city_suggestions'|'location_input'|'custom'} ContentSectionType
 */

/**
 * @typedef {Object} ContentSection
 * @property {ContentSectionType} type - Type of content section
 * @property {string} [title] - Section title
 * @property {string|React.ReactNode} content - Section content
 * @property {string} [icon] - Icon for the section
 * @property {ContentAction[]} [actions] - Action buttons
 * @property {boolean} [loading] - Loading state
 * @property {string} [error] - Error message
 */

/**
 * @typedef {Object} ContentAction
 * @property {string} label - Button label
 * @property {Function} onClick - Click handler
 * @property {string} [variant] - Button variant (primary, secondary, danger, ghost)
 * @property {string} [icon] - Button icon
 * @property {boolean} [disabled] - Disabled state
 */

/**
 * @typedef {Object} ComponentState
 * @property {boolean} loading - Loading state
 * @property {string|null} error - Error message
 * @property {any} data - Component data
 */

/**
 * @typedef {Object} EventHandlers
 * @property {Function} [onImageError] - Image error handler
 * @property {Function} [onImageLoad] - Image load handler
 * @property {Function} [onLocationSelect] - Location selection handler
 * @property {Function} [onNeighborhoodSelect] - Neighborhood selection handler
 * @property {Function} [onSearch] - Search handler
 * @property {Function} [onRetry] - Retry handler
 */

/**
 * @typedef {Object} AccessibilityProps
 * @property {string} [ariaLabel] - ARIA label
 * @property {string} [ariaDescribedBy] - ARIA described by
 * @property {string} [role] - ARIA role
 * @property {number} [tabIndex] - Tab index
 */

/**
 * @typedef {Object} ComponentConfig
 * @property {string} [theme] - Theme (light, dark, auto)
 * @property {boolean} [animation] - Animation enabled
 * @property {boolean} [responsive] - Responsive design
 * @property {boolean} [accessibility] - Accessibility features
 * @property {boolean} [loading] - Loading state
 * @property {string} [error] - Error message
 */

/**
 * @typedef {Object} BaseComponentProps
 * @property {EventHandlers} [eventHandlers] - Event handlers
 * @property {AccessibilityProps} [accessibilityProps] - Accessibility props
 * @property {ComponentConfig} [config] - Component configuration
 * @property {string} [className] - CSS class name
 * @property {Object} [style] - Inline styles
 * @property {React.ReactNode} [children] - Child components
 */

/**
 * @typedef {Object} LocationHeroProps
 * @property {Location} location - Location information
 * @property {ImageSource[]} images - Array of images
 * @property {boolean} [loading] - Loading state
 * @property {Function} [onError] - Error handler
 */

/**
 * @typedef {Object} ContentSectionProps
 * @property {ContentSection[]} sections - Array of content sections
 * @property {string} [layout] - Layout type (vertical, horizontal, grid)
 * @property {string} [spacing] - Spacing between sections
 */

/**
 * @typedef {Object} LocationGuideProps
 * @property {LocationWithCoords} location - Location with coordinates
 * @property {Neighborhood[]} [neighborhoods] - Array of neighborhoods
 * @property {ImageSource[]} [images] - Array of images
 * @property {ContentSection[]} [sections] - Array of content sections
 * @property {boolean} [showNeighborhoodPicker] - Show neighborhood picker
 * @property {boolean} [showSearch] - Show search functionality
 * @property {boolean} [showSuggestions] - Show location suggestions
 */

/**
 * @typedef {Object} LocationInputProps
 * @property {string} value - Input value
 * @property {string} [placeholder] - Input placeholder
 * @property {Location[]} [suggestions] - Location suggestions
 * @property {Function} onInputChange - Input change handler
 * @property {Function} [onSuggestionSelect] - Suggestion selection handler
 * @property {Function} [onSearch] - Search handler
 */

// Type guards for runtime type checking

/**
 * Check if object is a valid Location
 * @param {any} obj - Object to check
 * @returns {boolean} True if valid Location
 */
export function isLocation(obj) {
    return obj && typeof obj.name === 'string';
}

/**
 * Check if object is a valid Neighborhood
 * @param {any} obj - Object to check
 * @returns {boolean} True if valid Neighborhood
 */
export function isNeighborhood(obj) {
    return obj && typeof obj.name === 'string';
}

/**
 * Check if object is a valid ImageSource
 * @param {any} obj - Object to check
 * @returns {boolean} True if valid ImageSource
 */
export function isImageSource(obj) {
    return obj && typeof obj.url === 'string';
}

/**
 * Check if object is a valid ContentSection
 * @param {any} obj - Object to check
 * @returns {boolean} True if valid ContentSection
 */
export function isContentSection(obj) {
    return obj && obj.type && obj.content;
}

// Utility functions for creating objects

/**
 * Create a Location object
 * @param {string} name - Location name
 * @param {string} [country] - Country name
 * @param {string} [state] - State name
 * @returns {Location} Location object
 */
export const createLocation = (name, country, state) => ({
    name,
    country,
    state
});

/**
 * Create a Neighborhood object
 * @param {string} name - Neighborhood name
 * @param {string} [description] - Neighborhood description
 * @returns {Neighborhood} Neighborhood object
 */
export const createNeighborhood = (name, description) => ({
    name,
    description
});

/**
 * Create an ImageSource object
 * @param {string} url - Image URL
 * @param {string} [alt] - Alternative text
 * @returns {ImageSource} ImageSource object
 */
export const createImageSource = (url, alt) => ({
    url,
    alt
});

/**
 * Create a ContentSection object
 * @param {ContentSectionType} type - Section type
 * @param {string|React.ReactNode} content - Section content
 * @param {string} [title] - Section title
 * @returns {ContentSection} ContentSection object
 */
export const createContentSection = (type, content, title) => ({
    type,
    title,
    content
});

// Common validation functions

/**
 * Validate location object
 * @param {Location} location - Location to validate
 * @returns {boolean} True if valid
 */
export function validateLocation(location) {
    return isLocation(location) && location.name.trim().length > 0;
}

/**
 * Validate image source
 * @param {ImageSource} image - Image to validate
 * @returns {boolean} True if valid
 */
export function validateImage(image) {
    return isImageSource(image) && image.url.trim().length > 0;
}

/**
 * Validate content section
 * @param {ContentSection} section - Section to validate
 * @returns {boolean} True if valid
 */
export function validateContentSection(section) {
    return isContentSection(section) && 
           section.type && 
           section.content !== undefined;
}

// Constants for component types
export const CONTENT_SECTION_TYPES = {
    FUN_FACT: 'fun_fact',
    NEIGHBORHOOD_INFO: 'neighborhood_info',
    SEARCH_RESULTS: 'search_results',
    CITY_SUGGESTIONS: 'city_suggestions',
    LOCATION_INPUT: 'location_input',
    CUSTOM: 'custom'
};

export const LAYOUT_TYPES = {
    VERTICAL: 'vertical',
    HORIZONTAL: 'horizontal',
    GRID: 'grid'
};

export const SPACING_TYPES = {
    NONE: 'none',
    SMALL: 'small',
    MEDIUM: 'medium',
    LARGE: 'large'
};

export const THEME_TYPES = {
    LIGHT: 'light',
    DARK: 'dark',
    AUTO: 'auto'
};

export const BUTTON_VARIANTS = {
    PRIMARY: 'primary',
    SECONDARY: 'secondary',
    DANGER: 'danger',
    GHOST: 'ghost'
};