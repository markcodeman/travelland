const DEFAULT_HERO = 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=80';
const DEFAULT_VENUE = 'https://images.unsplash.com/photo-1445019980597-93fa8acb246c?auto=format&fit=crop&w=800&q=80';

const HERO_FALLBACKS = {
  paris: {
    url: 'https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=1600&q=80',
    photographer: 'Pierre Blaché',
    profileUrl: 'https://unsplash.com/@pierreblache'
  },
  london: {
    url: 'https://images.unsplash.com/photo-1431440869543-efaf3388c585?auto=format&fit=crop&w=1600&q=80',
    photographer: 'Luke Stackpoole',
    profileUrl: 'https://unsplash.com/@lukestack'
  },
  tokyo: {
    url: 'https://images.unsplash.com/photo-1505060280389-60df856a37e0?auto=format&fit=crop&w=1600&q=80',
    photographer: 'Javier Miranda',
    profileUrl: 'https://unsplash.com/@javiermiranda'
  },
  'new york': {
    url: 'https://images.unsplash.com/photo-1469478712025-ead91e0b867b?auto=format&fit=crop&w=1600&q=80',
    photographer: 'David Vives',
    profileUrl: 'https://unsplash.com/@davidvives'
  },
  bangkok: {
    url: 'https://images.unsplash.com/photo-1618889128235-93807ca6b114?q=80&w=1600&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D',
    photographer: 'Rizky Ananda',
    profileUrl: 'https://unsplash.com/@rizkyananda'
  },
  barcelona: {
    url: 'https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=1600&q=80',
    photographer: 'Enric Cruz López',
    profileUrl: 'https://unsplash.com/@enriccruzlopez'
  },
  rome: {
    url: 'https://images.unsplash.com/photo-1489515217757-5fd1be406fef?auto=format&fit=crop&w=1600&q=80',
    photographer: 'Cameron Venti',
    profileUrl: 'https://unsplash.com/@cameronventi'
  }
};

const VENUE_FALLBACKS = {
  bangkok: {
    default: [
      {
        url: 'https://images.unsplash.com/photo-1616047493036-0e1d5ab21dab?w=800&auto=format&fit=crop&q=80&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MjN8fGJhbmdrb2t8ZW58MHwwfDB8fHww',
        photographer: 'Rizky Ananda',
        profileUrl: 'https://unsplash.com/@rizkyananda'
      },
      {
        url: 'https://images.unsplash.com/photo-1550487221-3750d2cb0b3c?w=800&auto=format&fit=crop&q=80&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D',
        photographer: 'Rizky Ananda',
        profileUrl: 'https://unsplash.com/@rizkyananda'
      },
      {
        url: 'https://images.unsplash.com/photo-1528181304800-259b08848526?w=800&auto=format&fit=crop&q=80&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MzJ8fGJhbmdrb2t8ZW58MHwwfDB8fHww',
        photographer: 'Rizky Ananda',
        profileUrl: 'https://unsplash.com/@rizkyananda'
      }
    ],
    food: [
      {
        url: 'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80',
        photographer: 'Maehl Thomas',
        profileUrl: 'https://unsplash.com/@maehlthomas'
      },
      {
        url: 'https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=800&q=80',
        photographer: 'Maehl Thomas',
        profileUrl: 'https://unsplash.com/@maehlthomas'
      }
    ],
    nightlife: [
      {
        url: 'https://images.unsplash.com/photo-1505761671935-60b3a7427bad?auto=format&fit=crop&w=800&q=80',
        photographer: 'Maehl Thomas',
        profileUrl: 'https://unsplash.com/@maehlthomas'
      }
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

const buildPixabayUrl = (query, perPage = 6) => {
  const key = import.meta.env.VITE_PIXABAY_KEY;
  if (!key) return null;
  const params = new URLSearchParams({
    key,
    q: query,
    image_type: 'photo',
    orientation: 'horizontal',
    per_page: String(perPage),
    safesearch: 'true'
  });
  return `https://pixabay.com/api/?${params.toString()}`;
};

const UNSPLASH_BASE = 'https://api.unsplash.com';

const fetchUnsplashPhotos = async (query, perPage = 1) => {
  const key = import.meta.env.VITE_UNSPLASH_KEY;
  console.log('Unsplash API check:', { key: key ? 'exists' : 'missing', query, perPage });
  if (!key) return null;

  const params = new URLSearchParams({
    query,
    per_page: String(perPage),
    orientation: 'landscape',
    content_filter: 'high'
  });

  try {
    const resp = await fetch(`${UNSPLASH_BASE}/search/photos?${params}`, {
      headers: {
        'Authorization': `Client-ID ${key}`
      }
    });
    console.log('Unsplash API response:', resp.status);
    if (!resp.ok) return null;
    const data = await resp.json();
    console.log('Unsplash API results:', data.results?.length || 0, 'photos for', query);
    return data.results;
  } catch (err) {
    console.warn('Unsplash API fetch failed', err);
    return null;
  }
};

export const getHeroImage = async (city) => {
  if (!city) return DEFAULT_HERO;

  // Try Unsplash API first
  const photos = await fetchUnsplashPhotos(`${city} skyline`, 1);
  if (photos?.length) {
    const photo = photos[0];
    // Trigger download event
    try {
      await fetch(photo.links.download_location, { method: 'GET' });
    } catch (err) {
      console.warn('Failed to trigger Unsplash download', err);
    }
    return photo.urls.regular || photo.urls.full;
  }

  // Wikimedia Commons fallback
  try {
    const wikiUrl = `https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=${encodeURIComponent(city + ' skyline')}&gsrlimit=1&prop=imageinfo&iiprop=url&format=json&origin=*`;
    const wikiResp = await fetch(wikiUrl);
    if (wikiResp.ok) {
      const wikiData = await wikiResp.json();
      const pages = wikiData?.query?.pages;
      if (pages) {
        const firstPage = Object.values(pages)[0];
        const img = firstPage?.imageinfo?.[0]?.url;
        if (img) return img;
      }
    }
  } catch (err) {
    console.warn('Wikimedia hero fetch failed', err);
  }

  // Curated Unsplash fallbacks (primary choice for quality)
  const fallbackKey = city.toLowerCase();
  const fallback = HERO_FALLBACKS[fallbackKey];
  return fallback?.url || DEFAULT_HERO;
};

export const getHeroImageMeta = async (city) => {
  if (!city) return { url: DEFAULT_HERO };

  // Try Unsplash API first
  const photos = await fetchUnsplashPhotos(`${city} skyline`, 1);
  if (photos?.length) {
    const photo = photos[0];
    return {
      url: photo.urls.regular || photo.urls.full,
      photographer: photo.user.name,
      profileUrl: photo.user.links.html,
      downloadUrl: photo.links.download_location
    };
  }
  
  const fallbackKey = city.toLowerCase();
  const fallback = HERO_FALLBACKS[fallbackKey];
  return fallback || { url: DEFAULT_HERO };
};

export const getVenueImages = async (city, category, count = 4) => {
  const metas = await getVenueImageMeta(city, category, count);
  return metas.map(meta => meta.url);
};

export const getVenueImageMeta = async (city, category, count = 4) => {
  if (!city) return Array(count).fill({ url: DEFAULT_VENUE });

  // Try Unsplash API first
  const query = `${city} ${category || 'landmark'}`;
  const photos = await fetchUnsplashPhotos(query, count);
  if (photos?.length) {
    // Trigger download events
    photos.forEach(photo => {
      try {
        fetch(photo.links.download_location, { method: 'GET' });
      } catch (err) {
        console.warn('Failed to trigger Unsplash download', err);
      }
    });

    return photos.map(photo => ({
      url: photo.urls.regular || photo.urls.full,
      photographer: photo.user.name,
      profileUrl: photo.user.links.html,
      downloadUrl: photo.links.download_location
    }));
  }

  // Fallback to curated images
  const fallbackCity = VENUE_FALLBACKS[city.toLowerCase()];
  const fallbackCategory = category ? fallbackCity?.[category.toLowerCase()] : null;
  const fallbackDefault = fallbackCity?.default;

  if (fallbackCategory?.length) {
    return Array(count).fill(0).map((_, idx) => {
      const item = fallbackCategory[idx % fallbackCategory.length];
      return typeof item === 'string' ? { url: item } : item;
    });
  }

  if (fallbackDefault?.length) {
    return Array(count).fill(0).map((_, idx) => {
      const item = fallbackDefault[idx % fallbackDefault.length];
      return typeof item === 'string' ? { url: item } : item;
    });
  }

  return Array(count).fill({ url: DEFAULT_VENUE });
};

// Trigger Unsplash download event (required by API guidelines)
export const triggerUnsplashDownload = async (imageUrl) => {
  try {
    // Extract photo ID from Unsplash URL
    const match = imageUrl.match(/unsplash\.com\/photos\/([a-zA-Z0-9_-]+)/);
    if (!match) return;
    
    const photoId = match[1];
    const downloadUrl = `https://api.unsplash.com/photos/${photoId}/download`;
    
    // Call download endpoint (no key required for trigger)
    await fetch(downloadUrl, { method: 'GET' });
  } catch (err) {
    console.warn('Failed to trigger Unsplash download', err);
  }
};
