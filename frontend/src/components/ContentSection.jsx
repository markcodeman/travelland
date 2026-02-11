import { useEffect, useRef } from 'react';
import './ContentSection.css';

/**
 * ContentSection Component
 * 
 * Unifies content display for different content types including:
 * - Fun facts
 * - Neighborhood information
 * - Search results
 * - City suggestions
 * - Location input
 * - Custom content
 * 
 * Features:
 * - Dynamic layout support (vertical, horizontal, grid)
 * - Spacing configuration
 * - Content type-specific styling
 * - Action buttons integration
 * - Loading and error states
 * 
 * Props:
 * - sections: ContentSection[]
 * - layout: 'vertical' | 'horizontal' | 'grid'
 * - spacing: 'none' | 'small' | 'medium' | 'large'
 */

const ContentSection = ({ 
    sections = [], 
    layout = 'vertical', 
    spacing = 'medium',
    className = ''
}) => {
    const sectionRef = useRef(null);

    useEffect(() => {
        if (sectionRef.current && sections.length > 0) {
            sectionRef.current.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'start' 
            });
        }
    }, [sections.length]);

    if (!sections || sections.length === 0) {
        return null;
    }

    const renderContent = (section) => {
        const { type, content, actions, loading, error } = section;

        // Loading state
        if (loading) {
            return (
                <div className="content-loading">
                    <div className="loading-spinner"></div>
                    <span>Loading...</span>
                </div>
            );
        }

        // Error state
        if (error) {
            return (
                <div className="content-error">
                    <div className="error-icon">⚠️</div>
                    <div className="error-message">{error}</div>
                    <button className="retry-btn">Retry</button>
                </div>
            );
        }

        // Content rendering based on type
        switch (type) {
            case 'fun_fact':
                return (
                    <div className="fun-fact-content">
                        <div className="fact-icon">💡</div>
                        <div className="fact-text">{content}</div>
                    </div>
                );

            case 'neighborhood_info':
                return (
                    <div className="neighborhood-content">
                        <div className="neighborhood-header">
                            <div className="hood-icon">🏘️</div>
                            <div className="hood-title">{section.title}</div>
                        </div>
                        <div className="hood-description">{content}</div>
                    </div>
                );

            case 'search_results':
                return (
                    <div className="search-results-content">
                        <div className="results-header">
                            <div className="results-icon">📍</div>
                            <div className="results-title">{section.title}</div>
                        </div>
                        <div className="results-content">{content}</div>
                    </div>
                );

            case 'city_suggestions':
                return (
                    <div className="city-suggestions-content">
                        <div className="suggestions-header">
                            <div className="suggestions-icon">🏙️</div>
                            <div className="suggestions-title">{section.title}</div>
                        </div>
                        <div className="suggestions-content">{content}</div>
                    </div>
                );

            case 'location_input':
                return (
                    <div className="location-input-content">
                        <div className="input-header">
                            <div className="input-icon">📍</div>
                            <div className="input-title">{section.title}</div>
                        </div>
                        <div className="input-content">{content}</div>
                    </div>
                );

            case 'custom':
                return (
                    <div className="custom-content">
                        {section.icon && <div className="custom-icon">{section.icon}</div>}
                        {section.title && <div className="custom-title">{section.title}</div>}
                        <div className="custom-body">{content}</div>
                    </div>
                );

            default:
                return <div className="default-content">{content}</div>;
        }
    };

    const renderActions = (actions) => {
        if (!actions || actions.length === 0) {
            return null;
        }

        return (
            <div className="content-actions">
                {actions.map((action, index) => (
                    <button
                        key={index}
                        className={`action-button ${action.variant || 'primary'}`}
                        onClick={action.onClick}
                        disabled={action.disabled}
                        aria-label={action.label}
                    >
                        {action.icon && <span className="action-icon">{action.icon}</span>}
                        <span className="action-label">{action.label}</span>
                    </button>
                ))}
            </div>
        );
    };

    const renderSection = (section, index) => {
        const sectionClasses = [
            'content-section',
            `section-${section.type}`,
            `layout-${layout}`,
            `spacing-${spacing}`,
            section.loading ? 'loading' : '',
            section.error ? 'error' : ''
        ].filter(Boolean).join(' ');

        return (
            <div key={index} className={sectionClasses}>
                {/* Section Header */}
                {section.title && (
                    <div className="section-header">
                        {section.icon && <span className="section-icon">{section.icon}</span>}
                        <h3 className="section-title">{section.title}</h3>
                    </div>
                )}

                {/* Section Content */}
                <div className="section-content">
                    {renderContent(section)}
                </div>

                {/* Section Actions */}
                {renderActions(section.actions)}
            </div>
        );
    };

    const containerClasses = [
        'content-sections-container',
        `layout-${layout}`,
        `spacing-${spacing}`,
        className
    ].filter(Boolean).join(' ');

    return (
        <div ref={sectionRef} className={containerClasses}>
            {sections.map((section, index) => renderSection(section, index))}
        </div>
    );
};

export default ContentSection;