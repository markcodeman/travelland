import React from 'react';

export default function VenueCard({ venue, onDirections, onMap, onSave, onAddToItinerary }) {
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
          <a
            href={venue.mapsUrl || venue.website || venue.osm_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 text-sm font-medium transition"
          >Open in Google Maps</a>
        )}
      </div>
    );
  }

  const getMapsUrl = (venue) => {
    if (venue.place_id) return `https://www.google.com/maps/place/?q=place_id:${venue.place_id}`;
    // Prioritize venue name + city over coordinates for better search results
    if (venue.name) {
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
        {venue.provider && (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">{(venue.provider || '').toString().toUpperCase()}</span>
        )}
        {venue.groq_score ? (
          <span className={`ml-2 text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded`} title={venue.groq_reason ? `${venue.groq_reason}` : 'AI suggested'}>{`AI ${Math.round((venue.groq_score || 0)*100)}%`}</span>
        ) : null}
      </div>
      {venue.image && (
        <div className="venue-image-container">
          <img 
            className="venue-image" 
            src={venue.image} 
            alt={venue.name} 
            onError={(e) => {
              // Fallback to placeholder if image fails to load
              e.target.src = `https://picsum.photos/seed/${encodeURIComponent(venue.name)}/400/200.jpg`;
            }}
          />
        </div>
      )}
      {!venue.image && (
        <div className="venue-image-container">
          <img 
            className="venue-image" 
            src={`https://picsum.photos/seed/${encodeURIComponent(venue.name + venue.address || '')}/400/200.jpg`}
            alt={venue.name}
          />
        </div>
      )}
      <div className="mb-2">
        {venue.address && <div className="text-gray-500 text-sm mb-1">{venue.address}</div>}
        {venue.description && <div className="text-gray-700 text-base">{venue.description}</div>}
      </div>
      <div className="flex gap-2 mt-2">
        {onAddToItinerary && (
          <button
            onClick={() => onAddToItinerary(venue)}
            className="inline-block bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700 text-sm font-medium transition"
          >Add to Itinerary</button>
        )}
        <a 
          href={getMapsUrl(venue)}
          target="_blank" 
          rel="noopener noreferrer"
          className="inline-block bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 text-sm font-medium transition"
        >
          Open in Google Maps
        </a>
      </div>
    </div>
  );
}
