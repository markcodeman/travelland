import { useEffect } from 'react';
import { triggerUnsplashDownload } from '../services/imageService';

const DEFAULT_HERO = 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=80';

const HeroImage = ({ city, intent, loading, heroImage, heroImageMeta }) => {
  if (!city && !loading) return null;

  const imageUrl = heroImage || DEFAULT_HERO;

  // Trigger Unsplash download event when image is displayed
  useEffect(() => {
    if (imageUrl && imageUrl !== DEFAULT_HERO) {
      triggerUnsplashDownload(imageUrl);
    }
  }, [imageUrl]);

  const getAltText = (cityName, userIntent) => {
    if (userIntent) {
      return `${cityName} • ${userIntent}`;
    }
    return `Stunning views of ${cityName}`;
  };

  return (
    <div className="mt-8">
      {loading ? (
        <div className="rounded-3xl overflow-hidden bg-slate-100 h-64 animate-pulse" />
      ) : (
        <div className="relative rounded-3xl overflow-hidden shadow-xl">
          <img
            src={imageUrl}
            alt={getAltText(city, intent)}
            className="w-full h-72 md:h-80 object-cover"
            onError={(e) => {
              if (!e.target.src.includes('cityscape')) {
                e.target.src = `https://source.unsplash.com/1200x600/?${city.toLowerCase().replace(/\s+/g, '-')},cityscape&auto=format&fit=crop`;
              }
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent" />
          <div className="absolute inset-0 flex flex-col justify-end p-6 text-white space-y-2">
            <h1 className="text-2xl md:text-3xl font-bold">{city}</h1>
            {intent && (
              <p className="text-sm md:text-base text-white/90">Discover {intent.split(',').join(' • ')}</p>
            )}
            <div className="text-xs text-white/80">
              Photo by <a className="underline" href={heroImageMeta.profileUrl ? `${heroImageMeta.profileUrl}?utm_source=travelland&utm_medium=referral` : 'https://unsplash.com'} target="_blank" rel="noopener noreferrer">{heroImageMeta.photographer || 'Unsplash'}</a> on <a className="underline" href="https://unsplash.com?utm_source=travelland&utm_medium=referral" target="_blank" rel="noopener noreferrer">Unsplash</a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HeroImage;
