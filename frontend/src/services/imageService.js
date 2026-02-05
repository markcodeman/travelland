const DEFAULT_HERO = 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=80';
const DEFAULT_VENUE = 'https://images.unsplash.com/photo-1445019980597-93fa8acb246c?auto=format&fit=crop&w=800&q=80';

// Category-specific fallback images for when APIs fail
const CATEGORY_FALLBACKS = {
  nightlife: 'https://images.unsplash.com/photo-1514362545857-3bc16c4c7d1b?auto=format&fit=crop&w=1600&q=80',
  bar: 'https://images.unsplash.com/photo-1514362545857-3bc16c4c7d1b?auto=format&fit=crop&w=1600&q=80',
  food: 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=1600&q=80',
  dining: 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=1600&q=80',
  restaurant: 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1600&q=80',
  coffee: 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1600&q=80',
  cafe: 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1600&q=80',
  culture: 'https://images.unsplash.com/photo-1566127444979-b3d2b654e3d7?auto=format&fit=crop&w=1600&q=80',
  museum: 'https://images.unsplash.com/photo-1566127444979-b3d2b654e3d7?auto=format&fit=crop&w=1600&q=80',
  historic: 'https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&w=1600&q=80',
  shopping: 'https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&w=1600&q=80',
  nature: 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=80',
  park: 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1600&q=80',
  beach: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1600&q=80',
  landmark: 'https://images.unsplash.com/photo-1533929736458-ca588d08c8be?auto=format&fit=crop&w=1600&q=80',
  default: 'https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?auto=format&fit=crop&w=1600&q=80'
};

const HERO_FALLBACKS = {
  paris: 'https://images.unsplash.com/photo-1768201200491-f3f2439f807c?auto=format&fit=crop&w=1600&q=80',
  london: 'https://images.unsplash.com/photo-1431440869543-efaf3388c585?auto=format&fit=crop&w=1600&q=80',
  tokyo: 'https://images.unsplash.com/photo-1505060280389-60df856a37e0?auto=format&fit=crop&w=1600&q=80',
  'new york': 'https://images.unsplash.com/photo-1469478712025-ead91e0b867b?auto=format&fit=crop&w=1600&q=80',
  bangkok: 'https://images.unsplash.com/photo-1618889128235-93807ca6b114?q=80&w=1600&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D',
  barcelona: 'https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=1600&q=80',
  rome: 'https://images.unsplash.com/photo-1489515217757-5fd1be406fef?auto=format&fit=crop&w=1600&q=80',
  hallstatt: 'https://images.unsplash.com/photo-1500530852021-4673b1e67461?auto=format&fit=crop&w=1600&q=80',
  dublin: 'https://images.unsplash.com/photo-1580118869285-a2b4cfa563b5?auto=format&fit=crop&w=1600&q=80',  // Dublin cityscape
  tokchon: 'https://picsum.photos/1600/600?random=1',  // Random industrial-style image
  tanchon: 'https://picsum.photos/1600/600?random=1',  // Random industrial-style image
  'tanch-n': 'https://picsum.photos/1600/600?random=1',  // Random industrial-style image
  'tanchon-dong': 'https://picsum.photos/1600/600?random=2',  // Random industrial-style image
  'tanch-n-dong': 'https://picsum.photos/1600/600?random=2'  // Random industrial-style image
};

const VENUE_FALLBACKS = {
  bangkok: {
    default: [
      'https://images.unsplash.com/photo-1616047493036-0e1d5ab21dab?w=800&auto=format&fit=crop&q=80&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MjN8fGJhbmdrb2t8ZW58MHwwfDB8fHww',
      'https://images.unsplash.com/photo-1550487221-3750d2cb0b3c?w=800&auto=format&fit=crop&q=80&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D',
      'https://images.unsplash.com/photo-1528181304800-259b08848526?w=800&auto=format&fit=crop&q=80&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MzJ8fGJhbmdrb2t8ZW58MHwwfDB8fHww'
    ],
    food: [
      'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=800&q=80'
    ],
    nightlife: [
      'https://images.unsplash.com/photo-1505761671935-60b3a7427bad?auto=format&fit=crop&w=800&q=80'
    ]
  },
  paris: {
    coffee: [
      'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1504753793650-d4a2b783c15e?auto=format&fit=crop&w=800&q=80'
    ],
    default: [
      'https://images.unsplash.com/photo-1423245611892-7fda089cfd4b?auto=format&fit=crop&w=800&q=80'
    ]
  }
};

const slugifyCity = (city = '') => city.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

const fetchCityCoordinates = async (city) => {
  try {
    const resp = await fetch('/geocode', {
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
  const token = import.meta.env.VITE_MAPILLARY_TOKEN;
  if (!token) return null;
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

const fetchUnsplashPhotos = async (query, perPage = 3) => {
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
    return data.photos;
  } catch (err) {
    console.warn('Unsplash proxy fetch failed', err);
    return null;
  }
};

const fetchPixabayPhoto = async (query, perPage = 3) => {
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
  
  const fallback = HERO_FALLBACKS[slug] ||
    CATEGORY_FALLBACKS[normalizedIntent] ||
    CATEGORY_FALLBACKS.default;
    
  console.log('Using fallback:', fallback);

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

  const tryPixabayFirst = Math.random() < 0.5;
  
  if (tryPixabayFirst) {
    // Try Pixabay first, then Unsplash
    try {
      const photos = await fetchPixabayPhoto(`${city} ${intent}`, 1);
      if (photos?.length > 0) {
        return photos[0].url;
      }
    } catch (err) {
      console.warn('Pixabay hero failed, trying Unsplash', err);
    }
    
    try {
      const photos = await fetchUnsplashPhotos(`${city} ${intent}`, 1);
      if (photos?.length > 0) {
        return photos[0].url;
      }
    } catch (err) {
      console.warn('Unsplash hero failed, using fallback', err);
    }
  } else {
    // Try Unsplash first, then Pixabay
    try {
      const photos = await fetchUnsplashPhotos(`${city} ${intent}`, 1);
      if (photos?.length > 0) {
        return photos[0].url;
      }
    } catch (err) {
      console.warn('Unsplash hero failed, trying Pixabay', err);
    }
    
    try {
      const photos = await fetchPixabayPhoto(`${city} ${intent}`, 1);
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

// Alias functions for compatibility
const getHeroImage = fetchCityHeroImage;
const getHeroImageMeta = async (city, intent = '') => {
  const slug = slugifyCity(city);
  console.log('getHeroImageMeta:', { city, slug, intent });
  
  // For Tanchon/Tokchon, return fallback meta immediately
  if (slug === 'tanch-n' || slug === 'tokchon' || slug === 'tanchon' || 
      slug === 'tanchon-dong' || slug === 'tanch-n-dong' ||
      city.toLowerCase().includes('tanch') || city.toLowerCase().includes('tokch')) {
    console.log('Using immediate meta fallback for', city);
    return {
      url: HERO_FALLBACKS[slug] || HERO_FALLBACKS['tanch-n'],
      photographer: 'Picsum',
      profileUrl: 'https://picsum.photos',
      description: `Industrial architecture in ${city}`
    };
  }
  
  try {
    const photos = await fetchUnsplashPhotos(`${city} ${intent}`, 1);
    if (photos?.length > 0) {
      const photo = photos[0];
      return {
        url: photo.url,
        photographer: photo.user?.name || 'Unsplash',
        profileUrl: photo.user?.profile_url || 'https://unsplash.com',
        description: photo.description || photo.alt_description || ''
      };
    }
  } catch (err) {
    console.warn('Hero image meta failed', err);
  }
  
  return {
    url: HERO_FALLBACKS[slugifyCity(city)] || DEFAULT_HERO,
    photographer: 'Unsplash',
    profileUrl: 'https://unsplash.com',
    description: `Travel photo of ${city}`
  };
};

export {
  fetchCityHeroImage,
  fetchVenueImages,
  fetchUnsplashPhotos,
  fetchPixabayPhoto,
  triggerUnsplashDownload,
  getHeroImage,
  getHeroImageMeta,
  buildImageQueries,
  DEFAULT_HERO,
  DEFAULT_VENUE
};
