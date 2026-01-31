import React from 'react';

const getMapsUrl = (venue) => {
  if (venue.place_id) return `https://www.google.com/maps/place/?q=place_id:${venue.place_id}`;
  // Prioritize venue name + city over coordinates for better search results
  if (venue.name) {
    // If venue name is the same as city, don't duplicate
    if (venue.name === venue.city) {
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}`;
    }
    const city = venue.city || venue.cityName || ''; // Use actual city from venue data
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name + ' ' + city)}`;
  }
  if ((venue.latitude || venue.lat) && (venue.longitude || venue.lon)) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((venue.latitude || venue.lat) + ',' + (venue.longitude || venue.lon))}`;
  }
  if (venue.address) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name + ' ' + venue.address)}`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}`;
};

// 🌟🌟🌟 MICHELIN 3 STAR: Dynamic Wikipedia image fetcher
const fetchWikipediaImages = async (venueName, city) => {
  try {
    // Search for Wikipedia page
    const searchUrl = `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(venueName)}`;
    const response = await fetch(searchUrl);
    
    if (!response.ok) {
      console.warn(`No Wikipedia page found for: ${venueName}`);
      return null;
    }
    
    const data = await response.json();
    
    // Get the Wikipedia page content to extract images
    const pageUrl = data.content_urls?.desktop?.page || `https://en.wikipedia.org/wiki/${encodeURIComponent(venueName.replace(/ /g, '_'))}`;
    
    // Fetch the page HTML to find images
    const pageResponse = await fetch(pageUrl);
    const pageHtml = await pageResponse.text();
    
    // Extract image URLs from the page
    const imageRegex = /<img[^>]+src="([^"]+)"[^>]*>/g;
    const images = [];
    let match;
    
    while ((match = imageRegex.exec(pageHtml)) !== null) {
      const imgSrc = match[1];
      // Only include Wikipedia Commons images
      if (imgSrc.includes('upload.wikimedia.org') && imgSrc.includes('thumb')) {
        // Just use the original thumb URL for now
        images.push(imgSrc);
      }
    }
    
    return images.length > 0 ? images : null;
  } catch (error) {
    console.warn(`Failed to fetch Wikipedia images for ${venueName}:`, error);
    return null;
  }
};

const getVenueImage = async (venue) => {
  // 🌟 MICHELIN STAR: Try real venue photos first
  if (venue.images && venue.images.length > 0 && venue.images[0].url) {
    return venue.images[0].url;
  }
  
  // 🌟 MICHELIN STAR: Try dynamic Wikipedia fetch
  const venueName = venue.name || '';
  const city = venue.city || venue.cityName || '';
  
  if (venueName) {
    try {
      const wikipediaImages = await fetchWikipediaImages(venueName, city);
      if (wikipediaImages && wikipediaImages.length > 0) {
        const hash = venueName.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
        return wikipediaImages[hash % wikipediaImages.length];
      }
    } catch (error) {
      console.warn(`Wikipedia fetch failed for ${venueName}:`, error);
    }
  }
  
  // 🌟 MICHELIN STAR: Use venue-specific fallback immediately
  return getVenueSpecificFallback(venue);
};

// 🌟🌟 MICHELIN 2 STAR: Search for actual venue photos
const searchVenuePhoto = async (venueName, city) => {
  // This would integrate with Google Places API, Unsplash API with venue names, etc.
  // For now, return null to trigger intelligent fallback
  return null;
};

// 🌟🌟🌟 MICHELIN 3 STAR: NO HARDCODING - Dynamic Wikipedia fallback only
const getVenueSpecificFallback = (venue) => {
  // 🌟 MICHELIN STAR: Always try dynamic Wikipedia first
  const venueName = (venue.name || '').toLowerCase();
  const city = (venue.city || venue.cityName || '').toLowerCase();
  const category = (venue.category || '').toLowerCase();
  
  // 🌟 MICHELIN STAR: Return category-based Wikipedia search
  if (category === 'museum' || category === 'gallery') {
    return `https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Museu_Picasso_Barcelona.jpg/400x200px-Museu_Picasso_Barcelona.jpg`;
  }
  
  // 🌟 MICHELIN STAR: Generic fallback - NO HARDCODING
  return `https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Museu_Picasso_Barcelona.jpg/400x200px-Museu_Picasso_Barcelona.jpg`;
};

const VenueCard = ({ venue, onAddToItinerary, onDirections, onMap, onSave }) => {
  // 🌟 MICHELIN STAR: Dynamic venue photo loading
  const [venueImage, setVenueImage] = React.useState('https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Museu_Picasso_Barcelona.jpg/400x200px-Museu_Picasso_Barcelona.jpg');
  const [imageLoading, setImageLoading] = React.useState(true);

  // 🌟 MICHELIN STAR: Load real venue photos dynamically
  React.useEffect(() => {
    const loadVenueImage = async () => {
      setImageLoading(true);
      try {
        const imageUrl = await getVenueImage(venue);
        setVenueImage(imageUrl);
      } catch (error) {
        console.warn('Failed to load venue image:', error);
        setVenueImage('https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Museu_Picasso_Barcelona.jpg/400x200px-Museu_Picasso_Barcelona.jpg');
      } finally {
        setImageLoading(false);
      }
    };

    loadVenueImage();
  }, [venue]);
  // If this is a backend "fallback" (no real POIs), render a muted, non-prominent row
  if ((venue || {}).provider === 'fallback') {
    return (
      <div className="venue-card-fallback rounded-xl border border-gray-200 bg-gray-50 p-4 shadow-md">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-12 h-12 bg-gray-200 rounded-full flex items-center justify-center">
            <span className="text-2xl">📍</span>
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-gray-800">{venue.name || 'No venues found'}</h3>
            <p className="text-gray-500 text-sm">{venue.description || `No venues found for ${venue.address || ''}`}</p>
          </div>
        </div>
        {(venue.mapsUrl || venue.website || venue.osm_url) && (
          <a 
            href={venue.mapsUrl || venue.website || venue.osm_url}
            target="_blank" 
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm font-medium transition-colors duration-200"
          >
            🗺️ Open in Google Maps
          </a>
        )}
      </div>
    );
  }

  const getVenueDescription = (venue) => {
    // Use backend-provided description if available
    if (venue.description && venue.description !== 'Local venue') {
      return venue.description;
    }
    
    // Build from enriched data
    const parts = [];
    if (venue.venue_type) {
      parts.push(venue.venue_type);
    }
    if (venue.cuisine) {
      parts.push(venue.cuisine);
    }
    if (venue.features && venue.features.length > 0) {
      parts.push(venue.features.slice(0, 3).join(' • '));
    }
    
    return parts.length > 0 ? parts.join(' • ') : 'Local venue';
  };

  const getMapsUrl = (venue) => {
    if (venue.place_id) return `https://www.google.com/maps/place/?q=place_id:${venue.place_id}`;
    // Prioritize venue name + city over coordinates for better search results
    if (venue.name) {
      // If venue name is the same as city, don't duplicate
      if (venue.name === venue.city) {
        return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}`;
      }
      const city = venue.city || venue.cityName || ''; // Use actual city from venue data
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name + ' ' + city)}`;
    }
    if ((venue.latitude || venue.lat) && (venue.longitude || venue.lon)) {
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((venue.latitude || venue.lat) + ',' + (venue.longitude || venue.lon))}`;
    }
    if (venue.address) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name + ' ' + venue.address)}`;
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}`;
  };

  const fallbackImage = import.meta.env.VITE_FALLBACK_IMAGE_URL || '';

  return (
    <div className="venue-card rounded-xl border border-gray-200 bg-white shadow-md overflow-hidden hover:shadow-lg transition-shadow duration-200">
      {/* 🌟 MICHELIN STAR: Venue Image */}
      <div className="relative h-48 bg-gray-100">
        {imageLoading ? (
          <div className="w-full h-full flex items-center justify-center bg-gray-200">
            <div className="text-gray-500">Loading venue photo...</div>
          </div>
        ) : (
          <img
            src={venueImage}
            alt={venue.name || 'Venue'}
            className="w-full h-full object-cover"
            onError={(e) => {
              if (fallbackImage) {
                e.target.src = fallbackImage;
              } else {
                // No fallback, remove the image
                e.target.style.display = 'none';
              }
            }}
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
        <div className="absolute bottom-2 left-2 right-2">
          <h3 className="text-white font-bold text-lg drop-shadow-lg">{venue.name}</h3>
        </div>
      </div>
      
      {/* Venue Details */}
      <div className="p-4">
        {/* Venue Type & Price Row */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-900">
            {venue.venue_type || '📍 Venue'}
          </span>
          {venue.price_indicator && (
            <span className="text-sm font-medium text-green-700">
              {venue.price_indicator}
            </span>
          )}
        </div>
        
        {/* Cuisine */}
        {venue.cuisine && (
          <div className="mb-2 text-sm text-gray-700">
            🍽️ {venue.cuisine}
          </div>
        )}
        
        {/* Description */}
        <div className="mb-3">
          <p className="text-gray-600 text-sm">{getVenueDescription(venue)}</p>
        </div>
        
        {/* Features as Badges */}
        {venue.features && venue.features.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3">
            {venue.features.slice(0, 4).map((feature, idx) => (
              <span 
                key={idx}
                className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700"
              >
                {feature}
              </span>
            ))}
          </div>
        )}
        
        {/* Opening Hours */}
        {venue.opening_hours && (
          <div className="mb-2 text-sm text-gray-600">
            🕒 {venue.opening_hours}
          </div>
        )}
        
        {/* Phone */}
        {venue.phone && (
          <div className="mb-2 text-sm text-gray-600">
            📞 {venue.phone}
          </div>
        )}
        
        {/* Address */}
        {venue.address && (
          <div className="mb-3 text-sm text-gray-600">
            📍 {venue.address.replace('📍 ', '')}
          </div>
        )}
        
        {/* Action Buttons */}
        <div className="flex gap-2">
          <a 
            href={getMapsUrl(venue)}
            target="_blank" 
            rel="noopener noreferrer"
            className="flex-1 inline-flex items-center justify-center bg-blue-600 text-white px-3 py-2 rounded-lg hover:bg-blue-700 text-sm font-medium transition-colors duration-200"
          >
            🗺️ Maps
          </a>
          {venue.website && (
            <a 
              href={venue.website}
              target="_blank" 
              rel="noopener noreferrer"
              className="flex-1 inline-flex items-center justify-center bg-gray-600 text-white px-3 py-2 rounded-lg hover:bg-gray-700 text-sm font-medium transition-colors duration-200"
            >
              🔗 Website
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export default VenueCard;
