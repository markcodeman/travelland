
// Dynamic fallback loader with memoization
import FALLBACKS_DATA from './image_fallbacks.json';

let FALLBACKS = null;
let FALLBACKS_LOADING = false;
async function loadFallbacks() {
  if (FALLBACKS) return FALLBACKS;
  if (FALLBACKS_LOADING) {
    // Wait for ongoing load to complete
    await new Promise(resolve => {
      const check = () => {
        if (FALLBACKS) resolve();
        else setTimeout(check, 10);
      };
      check();
    });
    return FALLBACKS;
  }
  FALLBACKS_LOADING = true;
  try {
    // Use imported data instead of fetching
    FALLBACKS = FALLBACKS_DATA;
    return FALLBACKS;
  } finally {
    FALLBACKS_LOADING = false;
  }
}

// Default fallback images
const DEFAULT_HERO = 'https://picsum.photos/1600/900';
const DEFAULT_VENUE = 'https://picsum.photos/800/600';

// Example usage:
//   const { CATEGORY_FALLBACKS, HERO_FALLBACKS, VENUE_FALLBACKS } = await loadFallbacks();

const slugifyCity = (city = '') => city.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

const fetchCityCoordinates = async (city) => {
  try {
    const resp = await fetch('/api/geocode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ city })
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    const lat = data?.lat ?? data?.latitude;
    const lon = data?.lon ?? data?.longitude ?? data?.lng;
    if (typeof lat === 'number' && typeof lon === 'number') {
      return { lat, lon };
    }
  } catch (err) {
    console.warn('City geocode failed', err);
  }
  return null;
};

const fetchSourceUnsplashImage = (query) => {
  if (!query) return null;
  const encoded = encodeURIComponent(query);
  return {
    url: `https://source.unsplash.com/1600x900/?${encoded}`,
    photographer: 'Unsplash',
    profileUrl: 'https://unsplash.com'
  };
};

const fetchMapillaryImages = async (city, count = 4) => {
  const enabled = import.meta.env.VITE_ENABLE_MAPILLARY === 'true';
  const token = import.meta.env.VITE_MAPILLARY_TOKEN;
  if (!enabled || !token) return null;
  const coords = await fetchCityCoordinates(city);
  if (!coords) return null;
  try {
    const { lat, lon } = coords;
    const url = new URL('https://graph.mapillary.com/images');
    url.searchParams.set('access_token', token);
    url.searchParams.set('fields', 'thumb_640_url');
    url.searchParams.set('limit', String(count));
    url.searchParams.set('closeto', `${lon},${lat}`);
    const resp = await fetch(url.toString());
    if (!resp.ok) return null;
    const data = await resp.json();
    const items = data?.data;
    if (!Array.isArray(items) || !items.length) return null;
    return items
      .filter(item => item?.thumb_640_url)
      .slice(0, count)
      .map(item => item.thumb_640_url);
  } catch (err) {
    console.warn('Mapillary fetch failed', err);
    return null;
  }
};

// Legacy function - not used, backend proxy handles image fetching
const buildPixabayUrl = (query, perPage = 6) => {
  // Keys are handled by backend proxy, not frontend
  return null;
};

// Backend proxy handles all image API calls - no direct API access from frontend
// UNSPLASH_BASE and direct API keys removed for security

// Cache for unsplash results to prevent duplicate calls
const UNSPLASH_CACHE = new Map();

const fetchUnsplashPhotos = async (query, perPage = 3) => {
  const cacheKey = `${query}:${perPage}`;
  
  // Return cached result if available
  if (UNSPLASH_CACHE.has(cacheKey)) {
    console.log('Unsplash API check (cached):', { query, perPage });
    return UNSPLASH_CACHE.get(cacheKey);
  }
  
  console.log('Unsplash API check (secure proxy):', { query, perPage });
  
  try {
    const resp = await fetch('/api/unsplash-search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        query,
        per_page: perPage
      })
    });
    
    console.log('Unsplash proxy response:', resp.status);
    if (!resp.ok) return null;
    
    const data = await resp.json();
    console.log('Unsplash proxy results:', data.photos?.length || 0, 'photos for', query);
    
    // Cache the result
    UNSPLASH_CACHE.set(cacheKey, data.photos);
    return data.photos;
  } catch (err) {
    console.warn('Unsplash proxy fetch failed', err);
    return null;
  }
};

// Cache for pixabay results to prevent duplicate calls
const PIXABAY_CACHE = new Map();

const fetchPixabayPhoto = async (query, perPage = 3) => {
  const cacheKey = `${query}:${perPage}`;
  
  // Return cached result if available
  if (PIXABAY_CACHE.has(cacheKey)) {
    console.log('Pixabay API check (cached):', { query, perPage });
    return PIXABAY_CACHE.get(cacheKey);
  }
  
  console.log('Pixabay API check (secure proxy):', { query, perPage });
  
  try {
    const resp = await fetch('/api/pixabay-search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        query,
        per_page: perPage
      })
    });
    
    console.log('Pixabay proxy response:', resp.status);
    if (!resp.ok) return null;
    
    const data = await resp.json();
    console.log('Pixabay proxy results:', data.photos?.length || 0, 'photos for', query);
    
    // Cache the result
    PIXABAY_CACHE.set(cacheKey, data.photos);
    return data.photos;
  } catch (err) {
    console.warn('Pixabay proxy fetch failed', err);
    return null;
  }
};

const buildImageQueries = (city, intent) => {
  const normalizedIntent = intent ? intent.replace(/intent|category/gi, '').trim() : '';
  const baseQueries = [
    `${city} ${normalizedIntent}`.trim(),
    `${city} old town`,
    `${city} skyline`,
    `${city} city center`,
    `${city} travel photography`,
    `${city} aerial view`
  ].filter(Boolean);
  return baseQueries;
};

const fetchCityHeroImage = async (city, intent = '') => {
  const slug = slugifyCity(city);
  const normalizedIntent = intent.toLowerCase().trim();
  console.log('fetchCityHeroImage:', { city, slug, intent });
  
  // Load fallbacks dynamically
  const { HERO_FALLBACKS, CATEGORY_FALLBACKS } = await loadFallbacks();

  const fallback = HERO_FALLBACKS[slug] ||
    CATEGORY_FALLBACKS[normalizedIntent] ||
    CATEGORY_FALLBACKS.default;

  console.log('Using fallback:', fallback);

  // Hard-prefer R2 fallback for Bran Castle
  if (slug === 'bran-castle-romania' && fallback) {
    return fallback;
  }

  // For Tanchon/Tokchon, use fallback immediately to avoid API delays and Firefox CORS issues
  if (slug === 'tanch-n' || slug === 'tokchon' || slug === 'tanchon' || 
      slug === 'tanchon-dong' || slug === 'tanch-n-dong' ||
      city.toLowerCase().includes('tanch') || city.toLowerCase().includes('tokch') ||
      city.toLowerCase().includes('pyongyang') || city.toLowerCase().includes('north korea')) {
    console.log('Using immediate fallback for', city, slug);
    return fallback;
  }

  // Skip API calls entirely to avoid Firefox OpaqueResponseBlocking
  if (city.toLowerCase().includes('tanch') || city.toLowerCase().includes('tokch') ||
      city.toLowerCase().includes('pyongyang') || city.toLowerCase().includes('north korea')) {
    console.log('Skipping API calls for', city);
    return fallback;
  }

  // Special handling for ambiguous city names
  // "Natal" means "Christmas" in Portuguese - search needs to be specific
  const searchCity = city.toLowerCase().trim() === 'natal' ? 'Natal Brazil' : city;
  console.log('Search query:', { original: city, search: searchCity });

  const tryPixabayFirst = Math.random() < 0.5;
  
  if (tryPixabayFirst) {
    // Try Pixabay first, then Unsplash
    try {
      const photos = await fetchPixabayPhoto(`${searchCity} ${intent}`, 1);
      if (photos?.length > 0) {
        return photos[0].url;
      }
    } catch (err) {
      console.warn('Pixabay hero failed, trying Unsplash', err);
    }
    
    try {
      const photos = await fetchUnsplashPhotos(`${searchCity} ${intent}`, 1);
      if (photos?.length > 0) {
        return photos[0].url;
      }
    } catch (err) {
      console.warn('Unsplash hero failed, using fallback', err);
    }
  } else {
    // Try Unsplash first, then Pixabay
    try {
      const photos = await fetchUnsplashPhotos(`${searchCity} ${intent}`, 1);
      if (photos?.length > 0) {
        return photos[0].url;
      }
    } catch (err) {
      console.warn('Unsplash hero failed, trying Pixabay', err);
    }
    
    try {
      const photos = await fetchPixabayPhoto(`${searchCity} ${intent}`, 1);
      if (photos?.length > 0) {
        return photos[0].url;
      }
    } catch (err) {
      console.warn('Pixabay hero failed, using fallback', err);
    }
  }
  
  return fallback;
};

const fetchVenueImages = async (city, intent = '', count = 3) => {
  const slug = slugifyCity(city);
  const { VENUE_FALLBACKS } = await loadFallbacks();
  const fallback = VENUE_FALLBACKS[slug]?.[intent] || VENUE_FALLBACKS[slug]?.default || [DEFAULT_VENUE];
  
  // Randomly choose which API to try first for variety
  const tryPixabayFirst = Math.random() < 0.5;
  
  if (tryPixabayFirst) {
    // Try Pixabay first, then Unsplash
    try {
      const photos = await fetchPixabayPhoto(`${city} ${intent}`, count);
      if (photos?.length > 0) {
        return photos.map(photo => ({
          url: photo.url,
          photographer: photo.user || 'Pixabay',
          profileUrl: photo.links?.pixabay || 'https://pixabay.com',
          description: photo.description || ''
        }));
      }
    } catch (err) {
      console.warn('Pixabay venue failed, trying Unsplash', err);
    }
    
    try {
      const photos = await fetchUnsplashPhotos(`${city} ${intent}`, count);
      if (photos?.length > 0) {
        return photos.map(photo => ({
          url: photo.url,
          photographer: photo.user?.name || 'Unsplash',
          profileUrl: photo.user?.profile_url || 'https://unsplash.com',
          description: photo.description || photo.alt_description || ''
        }));
      }
    } catch (err) {
      console.warn('Unsplash venue failed, using fallback', err);
    }
  } else {
    // Try Unsplash first, then Pixabay
    try {
      const photos = await fetchUnsplashPhotos(`${city} ${intent}`, count);
      if (photos?.length > 0) {
        return photos.map(photo => ({
          url: photo.url,
          photographer: photo.user?.name || 'Unsplash',
          profileUrl: photo.user?.profile_url || 'https://unsplash.com',
          description: photo.description || photo.alt_description || ''
        }));
      }
    } catch (err) {
      console.warn('Unsplash venue failed, trying Pixabay', err);
    }
    
    try {
      const photos = await fetchPixabayPhoto(`${city} ${intent}`, count);
      if (photos?.length > 0) {
        return photos.map(photo => ({
          url: photo.url,
          photographer: photo.user || 'Pixabay',
          profileUrl: photo.links?.pixabay || 'https://pixabay.com',
          description: photo.description || ''
        }));
      }
    } catch (err) {
      console.warn('Pixabay venue failed, using fallback', err);
    }
  }
  
  return fallback.slice(0, count).map(url => ({
    url,
    photographer: 'Unsplash',
    profileUrl: 'https://unsplash.com',
    description: ''
  }));
};

// Function to trigger Unsplash download event (for attribution)
const triggerUnsplashDownload = (imageUrl) => {
  try {
    // Create a download event for Unsplash attribution
    const event = new CustomEvent('unsplashDownload', {
      detail: { imageUrl }
    });
    window.dispatchEvent(event);
  } catch (err) {
    console.warn('Failed to trigger Unsplash download event', err);
  }
};

// Cache for hero image and meta calls to prevent duplicates
const HERO_IMAGE_CACHE = new Map();
const HERO_META_CACHE = new Map();

// Alias functions for compatibility with caching
const getHeroImage = async (city, intent = '') => {
  const cacheKey = `${city}:${intent}`;
  
  // Return cached result if available
  if (HERO_IMAGE_CACHE.has(cacheKey)) {
    console.log('Hero image check (cached):', { city, intent });
    return HERO_IMAGE_CACHE.get(cacheKey);
  }
  
  console.log('Hero image check (live):', { city, intent });
  
  const result = await fetchCityHeroImage(city, intent);
  
  // Cache the result
  HERO_IMAGE_CACHE.set(cacheKey, result);
  return result;
};

const getHeroImageMeta = async (city, intent = '') => {
  const cacheKey = `${city}:${intent}`;
  
  // Return cached result if available
  if (HERO_META_CACHE.has(cacheKey)) {
    console.log('Hero meta check (cached):', { city, intent });
    return HERO_META_CACHE.get(cacheKey);
  }
  
  console.log('Hero meta check (live):', { city, intent });
  
  const slug = slugifyCity(city);
  console.log('getHeroImageMeta:', { city, slug, intent });
  
  // Load fallbacks dynamically
  const { HERO_FALLBACKS } = await loadFallbacks();
  
  // For Tanchon/Tokchon, return fallback meta immediately
  if (slug === 'tanch-n' || slug === 'tokchon' || slug === 'tanchon' || 
      slug === 'tanchon-dong' || slug === 'tanch-n-dong' ||
      city.toLowerCase().includes('tanch') || city.toLowerCase().includes('tokch')) {
    console.log('Using immediate meta fallback for', city);
    const result = {
      url: HERO_FALLBACKS[slug] || HERO_FALLBACKS['tanch-n'],
      photographer: 'Picsum',
      profileUrl: 'https://picsum.photos',
      description: `Industrial architecture in ${city}`
    };
    
    // Cache the result
    HERO_META_CACHE.set(cacheKey, result);
    return result;
  }
  
  try {
    const photos = await fetchUnsplashPhotos(`${city} ${intent}`, 1);
    if (photos?.length > 0) {
      const photo = photos[0];
      const result = {
        url: photo.url,
        photographer: photo.user?.name || 'Unsplash',
        profileUrl: photo.user?.profile_url || 'https://unsplash.com',
        description: photo.description || photo.alt_description || ''
      };
      
      // Cache the result
      HERO_META_CACHE.set(cacheKey, result);
      return result;
    }
  } catch (err) {
    console.warn('Hero image meta failed', err);
  }
  
  const result = {
    url: HERO_FALLBACKS[slugifyCity(city)] || DEFAULT_HERO,
    photographer: 'Unsplash',
    profileUrl: 'https://unsplash.com',
    description: `Travel photo of ${city}`
  };
  
  // Cache the result
  HERO_META_CACHE.set(cacheKey, result);
  return result;
};

export {
  buildImageQueries, DEFAULT_HERO,
  DEFAULT_VENUE, fetchCityHeroImage, fetchPixabayPhoto, fetchUnsplashPhotos, fetchVenueImages, getHeroImage,
  getHeroImageMeta, triggerUnsplashDownload
};

