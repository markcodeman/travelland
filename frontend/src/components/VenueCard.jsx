import React from 'react';

const getMapsUrl = (venue) => {
  if (venue.place_id) return `https://www.google.com/maps/place/?q=place_id:${venue.place_id}`;
  // Prioritize venue name + city over coordinates for better search results
  if (venue.name) {
    // If venue name is the same as city, don't duplicate
    if (venue.name === venue.city) {
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}`;
    }
    const city = venue.city || 'Tokyo'; // Default to Tokyo if no city specified
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name + ' ' + city)}`;
  }
  if ((venue.latitude || venue.lat) && (venue.longitude || venue.lon)) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((venue.latitude || venue.lat) + ',' + (venue.longitude || venue.lon))}`;
  }
  if (venue.address) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name + ' ' + venue.address)}`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}`;
};

const getVenueImage = (venue) => {
  // If venue has real images from provider, use the first one
  if (venue.images && venue.images.length > 0 && venue.images[0].url) {
    return venue.images[0].url;
  }
  
  // Map transport venues to appropriate Unsplash images as fallback
  const name = (venue.name || '').toLowerCase();
  if (name.includes('metro') || name.includes('subway')) {
    return 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=200&fit=crop';
  }
  if (name.includes('jr') || name.includes('train')) {
    return 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400&h=200&fit=crop';
  }
  if (name.includes('bus')) {
    return 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=200&fit=crop';
  }
  if (name.includes('station')) {
    return 'https://images.unsplash.com/photo-1513406798767-bf27b1c38249?w=400&h=200&fit=crop';
  }
  
  // Default city image for fallback
  return `https://picsum.photos/seed/${encodeURIComponent(venue.name)}/400/200.jpg`;
};

const VenueCard = ({ venue, onAddToItinerary, onDirections, onMap, onSave }) => {
  // If this is a backend "fallback" (no real POIs), render a muted, non-prominent row
  if ((venue || {}).provider === 'fallback') {
    return (
      <div className="venue-card-fallback rounded-xl border border-gray-100 bg-gray-50 p-4 shadow flex flex-col">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-2xl">📍</span>
          <span className="font-semibold text-gray-700 flex-1">{venue.name || 'No venues found'}</span>
        </div>
        <div className="text-gray-500 text-sm mb-2">{venue.description || `No venues found for ${venue.address || ''}`}</div>
        {(venue.mapsUrl || venue.website || venue.osm_url) && (
          <div className="flex gap-2 mt-2">
            <a 
              href={venue.mapsUrl || venue.website || venue.osm_url}
              target="_blank" 
              rel="noopener noreferrer"
              className="inline-block bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 text-sm font-medium transition"
            >
              Open in Google Maps
            </a>
          </div>
        )}
      </div>
    );
  }

  const getVenueDescription = (venue) => {
    if (venue.description) return venue.description;
    
    // Extract real info from tags
    const tags = venue.tags || '';
    const tagMap = {};
    tags.split(',').forEach(tag => {
      const [key, value] = tag.split('=');
      if (key && value) tagMap[key.trim()] = value.trim();
    });
    
    let description = [];
    
    // Add cuisine type
    if (tagMap.cuisine) {
      const cuisine = tagMap.cuisine.replace(';', ' & ');
      description.push(`${cuisine.charAt(0).toUpperCase() + cuisine.slice(1)} restaurant`);
    } else if (tagMap.amenity) {
      description.push(`${tagMap.amenity.charAt(0).toUpperCase() + tagMap.amenity.slice(1)}`);
    }
    
    // Add opening hours if available
    if (tagMap['opening_hours']) {
      description.push('Open daily');
    }
    
    // Add contact info
    if (tagMap['contact:phone']) {
      description.push('Phone available');
    }
    
    return description.length > 0 ? description.join(' • ') : 'Local dining spot';
  };

  const getMapsUrl = (venue) => {
    if (venue.place_id) return `https://www.google.com/maps/place/?q=place_id:${venue.place_id}`;
    // Prioritize venue name + city over coordinates for better search results
    if (venue.name) {
      // If venue name is the same as city, don't duplicate
      if (venue.name === venue.city) {
        return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}`;
      }
      const city = venue.city || 'Tokyo'; // Default to Tokyo if no city specified
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name + ' ' + city)}`;
    }
    if ((venue.latitude || venue.lat) && (venue.longitude || venue.lon)) {
      return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((venue.latitude || venue.lat) + ',' + (venue.longitude || venue.lon))}`;
    }
    if (venue.address) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name + ' ' + venue.address)}`;
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name)}`;
  };

  return (
    <div className="venue-card rounded-xl border border-gray-200 bg-white p-4 shadow-md flex flex-col">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-2xl">{venue.emoji || '📍'}</span>
        <span className="font-semibold text-gray-800 flex-1">{venue.name}</span>
      </div>
      <div className="mb-2">
        <div className="text-gray-700 text-base mb-2">{getVenueDescription(venue)}</div>
      </div>
      <div className="flex gap-2 mt-2">
        <a 
          href={getMapsUrl(venue)}
          target="_blank" 
          rel="noopener noreferrer"
          className="inline-block bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 text-sm font-medium transition"
        >
          Maps
        </a>
      </div>
    </div>
  );
}

export default VenueCard;
