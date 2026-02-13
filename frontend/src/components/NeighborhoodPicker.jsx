import { pinyin } from 'pinyin-pro';

const NeighborhoodPicker = ({ city, category, neighborhoods, onSelect, onSkip, loading = false, inline = false }) => {
  const chineseTranslations = {
    '外滩': 'The Bund',
    '南京路': 'Nanjing Road',
    '陆家嘴': 'Lujiazui',
    '豫园': 'Yu Garden',
    '静安寺': "Jing'an Temple",
    '新天地': 'Xintiandi',
    '田子坊': 'Tianzifang',
    '浦东': 'Pudong',
    '浦西': 'Puxi',
    '街道': 'District',
    '区': 'District',
    '镇': 'Town',
    '乡': 'Township',
    '村': 'Village',
  };

  const formatBilingualName = (name) => {
    // Check if name contains Chinese characters
    const hasChinese = /[\u4e00-\u9fff]/.test(name);
    const hasKorean = /[가-힣]/.test(name);
    
    if (hasChinese) {
      // First apply specific translations for landmarks
      let displayName = name;
      for (const [cn, en] of Object.entries(chineseTranslations)) {
        if (name.includes(cn)) {
          displayName = displayName.replace(cn, `${cn} (${en})`);
        }
      }
      
      // If no specific translation was applied, convert to pinyin
      if (displayName === name) {
        const pinyinName = pinyin(name, { toneType: 'none', type: 'string', separator: ' ' });
        // Capitalize each word
        const capitalized = pinyinName.replace(/\b\w/g, c => c.toUpperCase());
        displayName = `${name} (${capitalized})`;
      }
      
      return displayName;
    } else if (hasKorean) {
      // If it's Korean, try to extract English part if available, or just show Korean
      const englishMatch = name.match(/\(([^)]+)\)/);
      if (englishMatch) {
        // Format: Korean (English)
        const koreanPart = name.replace(/\s*\([^)]*\)/, '').trim();
        return `${koreanPart} (${englishMatch[1]})`;
      }
      // Just Korean, no English part available
      return name;
    } else {
      // If it's English, we could add Korean if we had a mapping
      // For now, just return as-is
      return name;
    }
  };

  const getCategoryEmoji = (type, name) => {
    const emojiMap = {
      'historic': '🏛️',
      'culture': '🎨',
      'nightlife': '🌙',
      'shopping': '🛍️',
      'food': '🍽️',
      'bar': '🍸',
      'pub': '🍺',
      'residential': '🏘️',
      'nature': '🌳',
      'beach': '🏖️',
      'waterfront': '🌊',
      'market': '🛒',
      'default': '📍'
    };
    
    // Check for specific neighborhood names
    const lowerName = (name || '').toLowerCase();
    if (lowerName.includes('beach') || lowerName.includes('coastal') || lowerName.includes('waterfront')) {
      return '🏖️';
    }
    if (lowerName.includes('park') || lowerName.includes('garden') || lowerName.includes('nature')) {
      return '🌳';
    }
    if (lowerName.includes('historic') || lowerName.includes('old town')) {
      return '🏛️';
    }
    if (lowerName.includes('market') || lowerName.includes('shopping')) {
      return '🛍️';
    }
    if (lowerName.includes('wine') || lowerName.includes('vineyard')) {
      return '🍷';
    }
    
    return emojiMap[type] || emojiMap['default'];
  };

  // Extract feature badges from OSM tags
  const getFeatureBadges = (hood) => {
    const tags = hood?.tags || {};
    const badges = [];
    
    // Historic landmarks
    if (tags.historic || tags.heritage || tags.castle || tags.ruins) {
      badges.push({ emoji: '🏛️', label: 'Historic' });
    }
    // Tourism/attractions
    if (tags.tourism === 'attraction' || tags.tourism === 'museum' || tags.tourism === 'gallery') {
      badges.push({ emoji: '🎯', label: 'Attractions' });
    }
    // Parks/nature
    if (tags.leisure === 'park' || tags.leisure === 'garden' || tags.natural) {
      badges.push({ emoji: '🌳', label: 'Parks' });
    }
    // Dining/food
    if (tags.amenity === 'restaurant' || tags.amenity === 'cafe' || tags.amenity === 'bar') {
      badges.push({ emoji: '🍽️', label: 'Dining' });
    }
    // Shopping
    if (tags.shop || tags.amenity === 'marketplace') {
      badges.push({ emoji: '🛍️', label: 'Shopping' });
    }
    // Beach/waterfront
    if (tags.natural === 'beach' || tags.beach) {
      badges.push({ emoji: '🏖️', label: 'Beach' });
    }
    // Entertainment
    if (tags.amenity === 'theatre' || tags.amenity === 'cinema') {
      badges.push({ emoji: '🎭', label: 'Entertainment' });
    }
    
    return badges.slice(0, 3); // Max 3 badges
  };

  const buildDescription = (name, description, type, badges) => {
    if (description && description.trim().length > 0) return description;
    if (badges && badges.length > 0) {
      const labels = badges.map(b => b.label).join(', ');
      return `${labels} area of ${city}.`;
    }
    if (type) return `Notable ${type} spot in ${city}.`;
    return `Area of ${city} worth exploring.`;
  };

  const getCategoryColor = (type) => {
    const colorMap = {
      'historic': '#8B4513',
      'culture': '#9C27B0',
      'nightlife': '#FF6B6B',
      'shopping': '#4CAF50',
      'food': '#FF9800',
      'bar': '#E91E63',
      'pub': '#795548',
      'residential': '#4CAF50',
      'nature': '#2E7D32',
      'beach': '#FF9800',
      'waterfront': '#03A9F4',
      'market': '#8BC34A',
      'default': '#667eea'
    };
    return colorMap[type] || colorMap['default'];
  };

  const Wrapper = ({ children }) => (
    <div className={inline ? '' : 'fixed inset-0 z-40 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4'}>
      <div className="w-full max-w-4xl mx-auto">
        <div className="rounded-2xl border border-slate-200 bg-white shadow-lg p-4 md:p-6">
          {children}
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <Wrapper>
        <div className="space-y-2">
          <h3 className="text-lg font-semibold">🎯 Finding Best Neighborhoods</h3>
          <p className="text-slate-600 text-sm">Discovering the perfect spots for {category} in {city}...</p>
        </div>
        <div className="flex flex-col items-center justify-center gap-3 py-10">
          <div className="h-12 w-12 border-4 border-slate-200 border-t-brand-orange rounded-full animate-spin" />
          <p className="text-slate-600 text-base">Scanning {city}'s neighborhoods...</p>
        </div>
      </Wrapper>
    );
  }

  if (!neighborhoods || neighborhoods.length === 0) {
    const genericNeighborhoods = [
      { name: `${city} Centre`, description: `Downtown area of ${city}`, type: 'culture' },
      { name: `${city} North`, description: `Northern area of ${city}`, type: 'residential' },
      { name: `${city} South`, description: `Southern area of ${city}`, type: 'residential' },
      { name: `${city} East`, description: `Eastern area of ${city}`, type: 'residential' },
      { name: `${city} West`, description: `Western area of ${city}`, type: 'residential' },
      { name: `${city} Old Town`, description: `Historic center of ${city}`, type: 'historic' },
    ];

    return (
      <Wrapper>
        <div className="space-y-2">
          <h3 className="text-lg font-semibold">🎯 Choose Area</h3>
          <p className="text-slate-600 text-sm">Where in {city} would you like to explore {category}?</p>
        </div>
        <div className="grid gap-2 grid-cols-2 sm:grid-cols-2 md:grid-cols-3">
          {genericNeighborhoods.map((hood, index) => (
            <button
              key={index}
              className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white hover:border-brand-orange hover:bg-brand-orange/5 transition p-2.5 text-left"
              onClick={() => onSelect(hood)}
            >
              <div className="text-2xl">{getCategoryEmoji(hood.type, hood.name)}</div>
              <div className="flex-1">
                <h4 className="text-sm font-semibold text-slate-900">{hood.name}</h4>
                <p className="text-xs text-slate-600 leading-relaxed">{hood.description}</p>
              </div>
              <div className="text-slate-400">→</div>
            </button>
          ))}
        </div>
        <div className="mt-4 text-right">
          <button className="inline-flex items-center gap-2 rounded-full bg-brand-orange text-white px-4 py-2 text-sm font-semibold shadow-sm hover:bg-brand-orangeDark" onClick={onSkip}>
            Skip — Search all of {city}
          </button>
        </div>
      </Wrapper>
    );
  }

  return (
    <Wrapper>
      <div className="space-y-2">
        <h3 className="text-lg font-semibold">🎯 Pick a Neighborhood</h3>
        <p className="text-slate-600 text-sm">{city} has distinct neighborhoods. Choose one to explore, then select what interests you.</p>
      </div>
      <div className="grid gap-2 grid-cols-2 sm:grid-cols-2 md:grid-cols-3">
        {neighborhoods.map((hood, index) => {
          const name = typeof hood === 'string' ? hood : hood.name;
          const descriptionRaw = typeof hood === 'string' ? '' : (hood.description || '');
          const type = typeof hood === 'string' ? 'culture' : (hood.type || 'culture');
          const badges = typeof hood === 'string' ? [] : getFeatureBadges(hood);
          const description = buildDescription(name, descriptionRaw, type, badges);
          return (
            <button
              key={index}
              className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white hover:border-brand-orange hover:bg-brand-orange/5 transition p-2.5 text-left"
              onClick={() => onSelect(typeof hood === 'string' ? { name: hood } : hood)}
            >
              <div className="text-2xl">{getCategoryEmoji(type, name)}</div>
              <div className="flex-1 space-y-1">
                <h4 className="text-sm font-semibold text-slate-900">{formatBilingualName(name)}</h4>
                <p className="text-xs text-slate-600 leading-relaxed">{description}</p>
                {badges.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {badges.map((badge, badgeIndex) => (
                      <span key={badgeIndex} className="px-1.5 py-0.5 text-[11px] rounded-full bg-slate-100 text-slate-700 font-semibold">
                        {badge.emoji} {badge.label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="text-slate-400">→</div>
            </button>
          );
        })}
      </div>
      <div className="mt-4 text-right">
        <button className="inline-flex items-center gap-2 rounded-full bg-brand-orange text-white px-4 py-2 text-sm font-semibold shadow-sm hover:bg-brand-orangeDark" onClick={onSkip}>
          Skip for now →
        </button>
      </div>
    </Wrapper>
  );
};

export default NeighborhoodPicker;
