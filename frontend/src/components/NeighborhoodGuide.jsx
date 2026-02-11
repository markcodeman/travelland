import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchCityHeroImage } from '../services/imageService';
import './NeighborhoodGuide.css';

// Simple cache for neighborhood images to prevent repeated API calls
const imageCache = new Map();

const NeighborhoodGuide = ({ city, neighborhood, onImageLoaded }) => {
  const [heroImage, setHeroImage] = useState('');
  const [heroImageMeta, setHeroImageMeta] = useState({});
  const [loading, setLoading] = useState(true);
  const [contentLoading, setContentLoading] = useState(true);
  const [neighborhoodContent, setNeighborhoodContent] = useState({
    tagline: '',
    funFact: '',
    exploration: ''
  });
  const fetchingRef = useRef(false);
  const mountedRef = useRef(true);

  // Fetch dynamic neighborhood content from existing API
  const fetchNeighborhoodContent = useCallback(async () => {
    if (!city || !neighborhood || fetchingRef.current) return;
    
    fetchingRef.current = true;
    
    try {
      const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5010';
      const response = await fetch(`${API_BASE}/api/generate_quick_guide`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          city: city,
          neighborhood: neighborhood
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        if (mountedRef.current) {
          // Use the dynamic content from the existing API
          setNeighborhoodContent({
            tagline: data.tagline || data.quick_guide || `Discover unique attractions and local experiences in ${neighborhood}.`,
            funFact: data.fun_fact || `${neighborhood} has fascinating local history and culture waiting to be discovered!`,
            exploration: data.exploration || `Explore ${neighborhood} and uncover the unique experiences that make this ${city} neighborhood special!`
          });
          console.log('[NEIGHBORHOOD-CONTENT] Dynamic content loaded:', { 
            city, 
            neighborhood, 
            source: data.source,
            dynamic: true
          });
        }
      } else {
        console.error('[NEIGHBORHOOD-CONTENT] Failed to fetch content:', response.status);
      }
    } catch (error) {
      console.error('[NEIGHBORHOOD-CONTENT] Error fetching content:', error);
      // Set fallback content
      if (mountedRef.current) {
        setNeighborhoodContent({
          tagline: `Discover unique attractions and local experiences in ${neighborhood}.`,
          funFact: `${neighborhood} has fascinating local history and culture waiting to be discovered!`,
          exploration: `Explore ${neighborhood} and uncover the unique experiences that make this ${city} neighborhood special!`
        });
      }
    } finally {
      if (mountedRef.current) {
        setContentLoading(false);
      }
      fetchingRef.current = false;
    }
  }, [city, neighborhood]);

  const fetchNeighborhoodImage = useCallback(async () => {
    // Prevent multiple simultaneous fetches
    if (fetchingRef.current || !city || !neighborhood) {
      return;
    }
    
    fetchingRef.current = true;
    
    if (!mountedRef.current) {
      fetchingRef.current = false;
      return;
    }
    
    setLoading(true);
    
    try {
      // Check cache first
      const cacheKey = `${city}-${neighborhood}`;
      if (imageCache.has(cacheKey)) {
        const cached = imageCache.get(cacheKey);
        if (mountedRef.current) {
          setHeroImage(cached.url);
          setHeroImageMeta(cached.meta || {});
          setLoading(false);
          if (onImageLoaded) onImageLoaded();
        }
        fetchingRef.current = false;
        return;
      }

      console.log('Fetching neighborhood image:', { city, neighborhood, query: `${neighborhood}, ${city}` });
      
      // Try to get a specific image for this neighborhood
      const imageData = await fetchCityHeroImage(city, neighborhood);
      console.log('fetchCityHeroImage returned:', imageData);
      
      if (mountedRef.current) {
        // If no neighborhood-specific image, try famous landmarks
        let finalImageData = imageData;
        if (!imageData) {
          // Try famous landmarks for this neighborhood
          const landmarkQueries = {
            'shibuya': ['Shibuya Crossing Tokyo', 'Shibuya Scramble Tokyo', 'Shibuya Hachiko Tokyo'],
            'shinjuku': ['Shinjuku Tokyo Skytree', 'Shinjuku Gyoen Tokyo', 'Kabukicho Tokyo'],
            'ginza': ['Ginza Tokyo shopping', 'Ginza intersection Tokyo', 'Ginza luxury Tokyo'],
            'harajuku': ['Harajuku Takeshita Tokyo', 'Harajuku fashion Tokyo', 'Meiji Jingu Tokyo'],
            'akihabara': ['Akihabara Electric Town Tokyo', 'Akihabara anime Tokyo', 'Akihabara electronics Tokyo'],
            'ueno': ['Ueno Park Tokyo', 'Ueno Zoo Tokyo', 'Tokyo National Museum Ueno'],
            'tamachi': ['Tamachi Station Tokyo', 'Tamachi business Tokyo'],
            'roppongi': ['Roppongi Hills Tokyo', 'Tokyo Tower Roppongi', 'Roppongi nightlife Tokyo'],
            'ikebukuro': ['Ikebukuro Sunshine City Tokyo', 'Ikebukuro shopping Tokyo'],
            'asakusa': ['Sensoji Temple Asakusa Tokyo', 'Tokyo Skytree Asakusa', 'Nakamise Asakusa Tokyo']
          };
          
          const landmarkKey = neighborhood.toLowerCase();
          if (landmarkQueries[landmarkKey]) {
            // Try each landmark query
            for (const query of landmarkQueries[landmarkKey]) {
              try {
                const landmarkData = await fetchCityHeroImage(city, query);
                if (landmarkData?.url) {
                  finalImageData = landmarkData;
                  console.log(`Found landmark image for ${neighborhood}: ${query}`);
                  break;
                }
              } catch (e) {
                console.log(`Landmark query failed: ${query}`);
              }
            }
          }
          
          // Final fallback to city image
          if (!finalImageData) {
            finalImageData = await fetchCityHeroImage(city);
          }
        }
        
        // Cache the result
        const result = {
          url: finalImageData || '',
          meta: {}
        };
        console.log('Setting hero image to:', result.url);
        imageCache.set(cacheKey, result);
        
        setHeroImage(result.url);
        setHeroImageMeta(result.meta);
      }
    } catch (error) {
      console.error('Failed to fetch neighborhood image:', error);
      if (mountedRef.current) {
        // Use fallback
        const cityImageData = await fetchCityHeroImage(city);
        setHeroImage(cityImageData || '');
        setHeroImageMeta({});
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
        if (onImageLoaded) onImageLoaded();
      }
      fetchingRef.current = false;
    }
  }, [city, neighborhood, onImageLoaded]);

  useEffect(() => {
    mountedRef.current = true;
    
    if (city && neighborhood) {
      fetchNeighborhoodImage();
      fetchNeighborhoodContent();
    }
    
    return () => {
      mountedRef.current = false;
    };
  }, [fetchNeighborhoodImage, fetchNeighborhoodContent, city, neighborhood]);

  if (!city || !neighborhood) {
    return null;
  }

  return (
    <div className="neighborhood-guide">
      <div className="neighborhood-hero">
        {loading ? (
          <div className="neighborhood-hero-loading">
            <div className="loading-pill" />
            <div className="loading-title loading-pulse" />
            <div className="loading-line loading-pulse" />
          </div>
        ) : (
          <>
            <img 
              src={heroImage} 
              alt={`${neighborhood}, ${city}`}
              className="neighborhood-hero-image"
              onError={(e) => {
                // Fallback to a generic image if load fails
                e.target.src = `https://images.unsplash.com/photo-1505060280389-60df856a37e0?auto=format&fit=crop&w=1600&q=80`;
              }}
            />
            <div className="neighborhood-hero-overlay">
              <div className="neighborhood-hero-content">
                <h1 className="neighborhood-title">{neighborhood}</h1>
                <p className="neighborhood-subtitle">🗼 {city}</p>
              </div>
            </div>
          </>
        )}
      </div>
      
      <div className="neighborhood-description">
        <div className="neighborhood-info">
          <div className="neighborhood-details">
            <p className="neighborhood-tagline">{contentLoading ? 'Loading...' : neighborhoodContent.tagline}</p>
            <div className="neighborhood-fun-fact">
              <span className="fun-fact-icon">💡</span>
              <span className="fun-fact-text">{contentLoading ? 'Loading fun fact...' : neighborhoodContent.funFact}</span>
            </div>
            <p className="neighborhood-exploration">{contentLoading ? 'Loading...' : neighborhoodContent.exploration}</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NeighborhoodGuide;
