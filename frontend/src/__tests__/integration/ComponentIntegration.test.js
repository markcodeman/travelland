/**
 * Component Integration Tests
 * 
 * Tests for the consolidated components to ensure they work together properly
 * and maintain backward compatibility during migration.
 */

import { jest } from '@jest/globals';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Import consolidated components
import ContentSection from '../../components/ContentSection';
import LocationGuide from '../../components/LocationGuide';
import LocationHero from '../../components/LocationHero';

// Import utilities
import {
    createContentSection,
    createImageSource,
    createLocation,
    createNeighborhood
} from '../../types/location';

// Mock data
const mockLocation = createLocation('Paris', 'France', 'Île-de-France');
const mockNeighborhoods = [
    createNeighborhood('Le Marais', 'Historic district with trendy shops and cafes'),
    createNeighborhood('Montmartre', 'Artistic neighborhood with the Sacré-Cœur'),
    createNeighborhood('Latin Quarter', 'Student area with bookshops and bistros')
];
const mockImages = [
    createImageSource('https://example.com/paris1.jpg', 'Eiffel Tower'),
    createImageSource('https://example.com/paris2.jpg', 'Louvre Museum')
];

const mockSections = [
    createContentSection('fun_fact', 'Paris has the most visited museum in the world!', 'Did You Know?'),
    createContentSection('neighborhood_info', 'Explore the charming streets of Le Marais.', 'Le Marais'),
    createContentSection('search_results', 'Top attractions in Paris.', 'Attractions')
];

// Mock functions
const mockOnLocationSelect = jest.fn();
const mockOnNeighborhoodSelect = jest.fn();
const mockOnSearch = jest.fn();

describe('Component Integration Tests', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        // Mock localStorage
        Object.defineProperty(window, 'localStorage', {
            value: {
                getItem: jest.fn(),
                setItem: jest.fn(),
                removeItem: jest.fn(),
                clear: jest.fn(),
            },
            writable: true,
        });
    });

    describe('LocationGuide Integration', () => {
        test('renders LocationGuide with all features enabled', () => {
            render(
                <LocationGuide
                    location={mockLocation}
                    neighborhoods={mockNeighborhoods}
                    images={mockImages}
                    sections={mockSections}
                    showNeighborhoodPicker={true}
                    showSearch={true}
                    showSuggestions={true}
                    onLocationSelect={mockOnLocationSelect}
                    onNeighborhoodSelect={mockOnNeighborhoodSelect}
                    onSearch={mockOnSearch}
                />
            );

            // Check if LocationHero is rendered
            expect(screen.getByRole('img', { name: /hero image for paris/i })).toBeInTheDocument();
            
            // Check if action buttons are present
            expect(screen.getByLabelText('Open search')).toBeInTheDocument();
            expect(screen.getByLabelText('Explore neighborhoods')).toBeInTheDocument();
            expect(screen.getByLabelText('View suggestions')).toBeInTheDocument();
        });

        test('handles neighborhood selection correctly', async () => {
            const user = userEvent.setup();
            
            render(
                <LocationGuide
                    location={mockLocation}
                    neighborhoods={mockNeighborhoods}
                    showNeighborhoodPicker={true}
                    onNeighborhoodSelect={mockOnNeighborhoodSelect}
                />
            );

            // Open neighborhood modal
            const neighborhoodBtn = screen.getByLabelText('Explore neighborhoods');
            await user.click(neighborhoodBtn);

            // Select a neighborhood
            const maraisBtn = screen.getByText('Le Marais');
            await user.click(maraisBtn);

            // Verify callback was called
            expect(mockOnNeighborhoodSelect).toHaveBeenCalledWith(mockNeighborhoods[0]);
        });

        test('handles search functionality correctly', async () => {
            const user = userEvent.setup();
            
            render(
                <LocationGuide
                    location={mockLocation}
                    showSearch={true}
                    onSearch={mockOnSearch}
                />
            );

            // Open search modal
            const searchBtn = screen.getByLabelText('Open search');
            await user.click(searchBtn);

            // Enter search query
            const searchInput = screen.getByPlaceholderText(/search for places/i);
            await user.type(searchInput, 'coffee shops');

            // Verify debounced search was called
            await waitFor(() => {
                expect(mockOnSearch).toHaveBeenCalledWith('coffee shops');
            }, { timeout: 400 });
        });

        test('manages local storage for recent and favorite locations', async () => {
            const user = userEvent.setup();
            
            render(
                <LocationGuide
                    location={mockLocation}
                    onLocationSelect={mockOnLocationSelect}
                />
            );

            // Simulate location selection
            const locationBtn = screen.getByText('Paris');
            await user.click(locationBtn);

            // Verify localStorage was called
            expect(window.localStorage.setItem).toHaveBeenCalledWith(
                'recent_locations',
                JSON.stringify([mockLocation])
            );
        });

        test('displays content sections correctly', () => {
            render(
                <LocationGuide
                    location={mockLocation}
                    sections={mockSections}
                />
            );

            // Check if content sections are rendered
            expect(screen.getByText('Did You Know?')).toBeInTheDocument();
            expect(screen.getByText('Le Marais')).toBeInTheDocument();
            expect(screen.getByText('Attractions')).toBeInTheDocument();
        });
    });

    describe('ContentSection Integration', () => {
        test('renders different content types correctly', () => {
            const sections = [
                createContentSection('fun_fact', 'This is a fun fact!', 'Fun Fact'),
                createContentSection('neighborhood_info', 'This is neighborhood info.', 'Neighborhood'),
                createContentSection('search_results', 'These are search results.', 'Results'),
                createContentSection('custom', 'This is custom content.', 'Custom')
            ];

            render(
                <ContentSection
                    sections={sections}
                    layout="vertical"
                    spacing="medium"
                />
            );

            // Check if all content types are rendered
            expect(screen.getByText('Fun Fact')).toBeInTheDocument();
            expect(screen.getByText('Neighborhood')).toBeInTheDocument();
            expect(screen.getByText('Results')).toBeInTheDocument();
            expect(screen.getByText('Custom')).toBeInTheDocument();
        });

        test('handles loading and error states', () => {
            const sections = [
                {
                    type: 'fun_fact',
                    title: 'Loading Test',
                    content: 'This should not show',
                    loading: true
                },
                {
                    type: 'neighborhood_info',
                    title: 'Error Test',
                    content: 'This should not show',
                    error: 'Something went wrong'
                }
            ];

            render(
                <ContentSection sections={sections} />
            );

            // Check loading state
            expect(screen.getByText('Loading...')).toBeInTheDocument();
            
            // Check error state
            expect(screen.getByText('Something went wrong')).toBeInTheDocument();
            expect(screen.getByText('Retry')).toBeInTheDocument();
        });

        test('handles action buttons correctly', async () => {
            const user = userEvent.setup();
            
            const sections = [
                {
                    type: 'fun_fact',
                    title: 'Test Section',
                    content: 'Test content',
                    actions: [
                        {
                            label: 'Action 1',
                            onClick: jest.fn(),
                            variant: 'primary'
                        },
                        {
                            label: 'Action 2',
                            onClick: jest.fn(),
                            variant: 'secondary'
                        }
                    ]
                }
            ];

            render(<ContentSection sections={sections} />);

            // Click action buttons
            const action1Btn = screen.getByText('Action 1');
            const action2Btn = screen.getByText('Action 2');
            
            await user.click(action1Btn);
            await user.click(action2Btn);

            // Verify callbacks were called
            expect(sections[0].actions[0].onClick).toHaveBeenCalled();
            expect(sections[0].actions[1].onClick).toHaveBeenCalled();
        });

        test('supports different layouts', () => {
            const sections = [
                createContentSection('fun_fact', 'Content 1', 'Section 1'),
                createContentSection('neighborhood_info', 'Content 2', 'Section 2')
            ];

            // Test vertical layout
            const { rerender } = render(
                <ContentSection sections={sections} layout="vertical" />
            );
            expect(screen.getByText('Section 1')).toBeInTheDocument();

            // Test horizontal layout
            rerender(<ContentSection sections={sections} layout="horizontal" />);
            expect(screen.getByText('Section 1')).toBeInTheDocument();

            // Test grid layout
            rerender(<ContentSection sections={sections} layout="grid" />);
            expect(screen.getByText('Section 1')).toBeInTheDocument();
        });
    });

    describe('LocationHero Integration', () => {
        test('renders hero component with images', () => {
            render(
                <LocationHero
                    location={mockLocation}
                    images={mockImages}
                    loading={false}
                />
            );

            // Check if hero is rendered
            expect(screen.getByRole('img', { name: /hero image for paris/i })).toBeInTheDocument();
        });

        test('handles image loading and errors', () => {
            const mockOnError = jest.fn();
            
            render(
                <LocationHero
                    location={mockLocation}
                    images={[]}
                    onError={mockOnError}
                />
            );

            // Should show placeholder when no images
            expect(screen.getByText('Location Image')).toBeInTheDocument();
        });
    });

    describe('Cross-Component Integration', () => {
        test('LocationGuide properly integrates with ContentSection', () => {
            render(
                <LocationGuide
                    location={mockLocation}
                    sections={mockSections}
                    showNeighborhoodPicker={false}
                    showSearch={false}
                    showSuggestions={false}
                />
            );

            // ContentSection should be rendered within LocationGuide
            expect(screen.getByText('Did You Know?')).toBeInTheDocument();
            expect(screen.getByText('Le Marais')).toBeInTheDocument();
        });

        test('Event handling flows correctly between components', async () => {
            const user = userEvent.setup();
            
            render(
                <LocationGuide
                    location={mockLocation}
                    neighborhoods={mockNeighborhoods}
                    onNeighborhoodSelect={mockOnNeighborhoodSelect}
                />
            );

            // Open modal and select neighborhood
            const neighborhoodBtn = screen.getByLabelText('Explore neighborhoods');
            await user.click(neighborhoodBtn);

            const maraisBtn = screen.getByText('Le Marais');
            await user.click(maraisBtn);

            // Verify the event flow worked correctly
            expect(mockOnNeighborhoodSelect).toHaveBeenCalledWith(mockNeighborhoods[0]);
        });

        test('State management works across component hierarchy', async () => {
            const user = userEvent.setup();
            
            render(
                <LocationGuide
                    location={mockLocation}
                    neighborhoods={mockNeighborhoods}
                    onLocationSelect={mockOnLocationSelect}
                />
            );

            // Select a location
            const locationBtn = screen.getByText('Paris');
            await user.click(locationBtn);

            // Verify state was updated and callback fired
            expect(mockOnLocationSelect).toHaveBeenCalledWith(mockLocation);
        });
    });

    describe('Accessibility Integration', () => {
        test('all components have proper ARIA labels', () => {
            render(
                <LocationGuide
                    location={mockLocation}
                    neighborhoods={mockNeighborhoods}
                />
            );

            // Check ARIA labels are present
            expect(screen.getByLabelText('Open search')).toBeInTheDocument();
            expect(screen.getByLabelText('Explore neighborhoods')).toBeInTheDocument();
            expect(screen.getByRole('img', { name: /hero image for paris/i })).toBeInTheDocument();
        });

        test('keyboard navigation works across components', async () => {
            const user = userEvent.setup();
            
            render(
                <LocationGuide
                    location={mockLocation}
                    showSearch={true}
                />
            );

            // Tab to search button and activate with Enter
            await user.tab();
            await user.keyboard('{Enter}');

            // Modal should be open
            expect(screen.getByText('Search Paris')).toBeInTheDocument();
        });
    });

    describe('Performance Integration', () => {
        test('components render efficiently with large datasets', () => {
            const largeNeighborhoods = Array.from({ length: 50 }, (_, i) => 
                createNeighborhood(`Neighborhood ${i}`, `Description ${i}`)
            );

            const startTime = performance.now();
            
            render(
                <LocationGuide
                    location={mockLocation}
                    neighborhoods={largeNeighborhoods}
                />
            );

            const renderTime = performance.now() - startTime;
            
            // Render should complete in reasonable time (less than 100ms)
            expect(renderTime).toBeLessThan(100);
        });

        test('debouncing works correctly in search integration', async () => {
            const user = userEvent.setup();
            
            render(
                <LocationGuide
                    location={mockLocation}
                    showSearch={true}
                    onSearch={mockOnSearch}
                />
            );

            const searchBtn = screen.getByLabelText('Open search');
            await user.click(searchBtn);

            const searchInput = screen.getByPlaceholderText(/search for places/i);
            
            // Type quickly - should only trigger search once after debounce
            await user.type(searchInput, 'coffee');
            await user.type(searchInput, ' shops');

            // Should only be called once after debounce delay
            await waitFor(() => {
                expect(mockOnSearch).toHaveBeenCalledTimes(1);
            }, { timeout: 400 });
        });
    });
});