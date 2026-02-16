import { pinyin } from 'pinyin-pro';
import { useMemo, useState } from 'react';

// Neighborhood categorization for smart grouping
const NEIGHBORHOOD_CATEGORIES = {
  'downtown': ['downtown', 'city center', 'centro', 'centre', 'central', 'cbd', 'business district'],
  'historic': ['historic', 'old town', 'old city', 'historic center', 'centro storico', 'altstadt', 'medina'],
  'artsy': ['arts', 'art', 'creative', 'bohemian', 'hipster', 'arts district', 'gallery', 'museum'],
  'foodie': ['food', 'culinary', 'restaurant', 'cafe', 'coffee', 'dining', 'eat', 'bistro', 'brunch'],
  'nightlife': ['nightlife', 'bars', 'clubs', 'pubs', 'night', 'entertainment', 'theater', 'cinema'],
  'shopping': ['shopping', 'mall', 'market', 'boutique', 'commercial', 'retail', 'stores'],
  'residential': ['residential', 'suburb', 'neighborhood', 'residence', 'housing', 'family'],
  'waterfront': ['waterfront', 'beach', 'coastal', 'harbor', 'port', 'river', 'lake', 'ocean'],
  'nature': ['park', 'garden', 'green', 'forest', 'mountain', 'nature', 'outdoors', 'trail']
};

const getNeighborhoodCategory = (name, description, tags) => {
  const text = `${name} ${description || ''}`.toLowerCase();
  const tagText = Object.keys(tags || {}).join(' ').toLowerCase();
  
  for (const [category, keywords] of Object.entries(NEIGHBORHOOD_CATEGORIES)) {
    for (const keyword of keywords) {
      if (text.includes(keyword) || tagText.includes(keyword)) {
        return category;
      }
    }
  }
  
  // Default categorization based on tags
  const tagKeys = Object.keys(tags || {});
  if (tagKeys.includes('historic') || tagKeys.includes('heritage')) return 'historic';
  if (tagKeys.includes('leisure') || tagKeys.includes('park')) return 'nature';
  if (tagKeys.includes('amenity') && (tagKeys.includes('restaurant') || tagKeys.includes('cafe'))) return 'foodie';
  if (tagKeys.includes('amenity') && (tagKeys.includes('bar') || tagKeys.includes('pub'))) return 'nightlife';
  if (tagKeys.includes('shop') || tagKeys.includes('marketplace')) return 'shopping';
  if (tagKeys.includes('natural') && (tagKeys.includes('beach') || tagKeys.includes('waterway'))) return 'waterfront';
  
  return 'residential';
};

const getCategoryDisplayName = (category) => {
  const displayNames = {
    'downtown': 'Downtown & Business',
    'historic': 'Historic & Cultural',
    'artsy': 'Arts & Creative',
    'foodie': 'Food & Dining',
    'nightlife': 'Nightlife & Entertainment',
    'shopping': 'Shopping & Markets',
    'residential': 'Residential & Local',
    'waterfront': 'Waterfront & Beach',
    'nature': 'Nature & Parks'
  };
  return displayNames[category] || category;
};

const getCategoryEmoji = (category) => {
  const emojis = {
    'downtown': '🏙️',
    'historic': '🏛️',
    'artsy': '🎨',
    'foodie': '🍽️',
    'nightlife': '🌙',
    'shopping': '🛍️',
    'residential': '🏘️',
    'waterfront': '🏖️',
    'nature': '🌳'
  };
  return emojis[category] || '📍';
};

const NeighborhoodPicker = ({ city, category, neighborhoods, onSelect, onSkip, loading = false, inline = false }) => {
  // State for filtering and grouping
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [showAll, setShowAll] = useState(false);
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'list'

  // Helper data and functions
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

  // Process neighborhoods with categorization
  const processedNeighborhoods = useMemo(() => {
    return (neighborhoods || []).map((hood) => {
      const name = typeof hood === 'string' ? hood : hood.name;
      const descriptionRaw = typeof hood === 'string' ? '' : (hood.description || '');
      const tags = typeof hood === 'string' ? {} : (hood.tags || {});
      const category = getNeighborhoodCategory(name, descriptionRaw, tags);
      
      return {
        ...hood,
        name,
        descriptionRaw,
        category,
        displayName: formatBilingualName(name),
        categoryDisplayName: getCategoryDisplayName(category),
        categoryEmoji: getCategoryEmoji(category)
      };
    });
  }, [neighborhoods]);

  // Filter neighborhoods based on search and category
  const filteredNeighborhoods = useMemo(() => {
    let filtered = processedNeighborhoods;
    
    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(hood => 
        hood.name.toLowerCase().includes(query) ||
        hood.descriptionRaw.toLowerCase().includes(query) ||
        hood.category.toLowerCase().includes(query) ||
        hood.categoryDisplayName.toLowerCase().includes(query)
      );
    }
    
    // Apply category filter
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(hood => hood.category === selectedCategory);
    }
    
    return filtered;
  }, [processedNeighborhoods, searchQuery, selectedCategory]);

  // Get unique categories for filtering
  const categories = useMemo(() => {
    const categorySet = new Set(processedNeighborhoods.map(hood => hood.category));
    return Array.from(categorySet).sort();
  }, [processedNeighborhoods]);

  // Determine which neighborhoods to show
  const neighborhoodsToShow = useMemo(() => {
    if (showAll) return filteredNeighborhoods;
    
    // Show top 6 neighborhoods by default for better UX
    return filteredNeighborhoods.slice(0, 6);
  }, [filteredNeighborhoods, showAll]);

  // Check if we should show "View All" button
  const shouldShowViewAll = filteredNeighborhoods.length > 6 && !showAll;

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
    const trimmed = (description || '').trim();
    const genericRe = new RegExp(`^(area|neighborhood) in ${city}`, 'i');
    const isGeneric = !trimmed || genericRe.test(trimmed);

    if (!isGeneric) return trimmed;
    if (badges && badges.length > 0) {
      const labels = badges.map(b => b.label).join(', ');
      return `${labels} area of ${city}.`;
    }
    if (type) return `${name} is a ${type} area in ${city}.`;
    return `${name} is an area of ${city} worth exploring.`;
  };

  const getCategoryChips = (hood) => {
    const tags = hood?.tags || {};
    const chips = [];
    if (tags.historic || tags.heritage || tags.castle || tags.ruins) chips.push({ emoji: '🏛️', label: 'Historic' });
    if (tags.tourism === 'attraction' || tags.tourism === 'museum' || tags.tourism === 'gallery') chips.push({ emoji: '🎯', label: 'Attractions' });
    if (tags.leisure === 'park' || tags.leisure === 'garden' || tags.natural) chips.push({ emoji: '🌳', label: 'Nature' });
    if (tags.amenity === 'restaurant' || tags.amenity === 'cafe' || tags.amenity === 'bar' || tags.amenity === 'pub') chips.push({ emoji: '🍽️', label: 'Food & Drink' });
    if (tags.shop || tags.amenity === 'marketplace') chips.push({ emoji: '🛍️', label: 'Shopping' });
    if (tags.natural === 'beach' || tags.beach || tags.waterway || tags.coastline) chips.push({ emoji: '🏖️', label: 'Waterfront' });
    if (tags.amenity === 'theatre' || tags.amenity === 'cinema') chips.push({ emoji: '🎭', label: 'Entertainment' });
    if (!chips.length && hood?.type) chips.push({ emoji: getCategoryEmoji(hood.type, hood.name), label: hood.type });
    return chips.slice(0, 3);
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
      <div className="space-y-4">
        <div className="space-y-2">
          <h3 className="text-lg font-semibold">🎯 Pick a Neighborhood</h3>
          <p className="text-slate-600 text-sm">{city} has distinct neighborhoods. Choose one to explore, then select what interests you.</p>
        </div>

        {/* Search and Filter Controls */}
        <div className="space-y-3">
          {/* Search Input */}
          <div className="relative">
            <input
              type="text"
              placeholder="Search neighborhoods..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-orange focus:border-transparent"
            />
            <div className="absolute left-3 top-2.5 text-slate-400">🔍</div>
          </div>

          {/* Category Filters */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedCategory('all')}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition ${
                selectedCategory === 'all'
                  ? 'bg-brand-orange text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              All Types
            </button>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition flex items-center gap-1 ${
                  selectedCategory === cat
                    ? 'bg-brand-orange text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                <span>{getCategoryEmoji(cat)}</span>
                <span>{getCategoryDisplayName(cat)}</span>
              </button>
            ))}
          </div>

          {/* Results Info */}
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>
              {filteredNeighborhoods.length} neighborhood{filteredNeighborhoods.length !== 1 ? 's' : ''} found
              {selectedCategory !== 'all' && ` in ${getCategoryDisplayName(selectedCategory)}`}
              {searchQuery && ` matching "${searchQuery}"`}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setViewMode('grid')}
                className={`px-2 py-1 rounded text-xs ${
                  viewMode === 'grid' ? 'bg-slate-200' : 'text-slate-500'
                }`}
              >
                Grid
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`px-2 py-1 rounded text-xs ${
                  viewMode === 'list' ? 'bg-slate-200' : 'text-slate-500'
                }`}
              >
                List
              </button>
            </div>
          </div>
        </div>

        {/* Neighborhood Grid */}
        <div className={`grid gap-2 ${
          viewMode === 'grid' 
            ? 'grid-cols-2 sm:grid-cols-2 md:grid-cols-3' 
            : 'grid-cols-1'
        }`}>
          {neighborhoodsToShow.map((hood, index) => {
            const name = hood.name;
            const descriptionRaw = hood.descriptionRaw;
            const category = hood.category;
            const categoryDisplayName = hood.categoryDisplayName;
            const categoryEmoji = hood.categoryEmoji;
            
            // Get feature badges from OSM tags
            const tags = typeof hood === 'string' ? {} : (hood.tags || {});
            const badges = getFeatureBadges(hood);
            const description = buildDescription(name, descriptionRaw, category, badges);
            
            return (
              <button
                key={index}
                className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white hover:border-brand-orange hover:bg-brand-orange/5 transition p-2.5 text-left"
                onClick={() => onSelect(typeof hood === 'string' ? { name: hood } : hood)}
              >
                <div className="text-2xl">{categoryEmoji}</div>
                <div className="flex-1 space-y-1">
                  <h4 className="text-sm font-semibold text-slate-900">{hood.displayName}</h4>
                  <p className="text-xs text-slate-600 leading-relaxed">{description}</p>
                  <div className="flex flex-wrap gap-1">
                    <span className="px-1.5 py-0.5 text-[11px] rounded-full bg-slate-100 text-slate-700 font-semibold">
                      {categoryEmoji} {categoryDisplayName}
                    </span>
                    {badges.length > 0 && badges.slice(0, 2).map((badge, badgeIndex) => (
                      <span key={badgeIndex} className="px-1.5 py-0.5 text-[11px] rounded-full bg-slate-100 text-slate-700 font-semibold">
                        {badge.emoji} {badge.label}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="text-slate-400">→</div>
              </button>
            );
          })}
        </div>

        {/* View All Button */}
        {shouldShowViewAll && (
          <div className="flex justify-center">
            <button
              onClick={() => setShowAll(true)}
              className="inline-flex items-center gap-2 rounded-full bg-slate-100 text-slate-700 px-4 py-2 text-sm font-semibold hover:bg-slate-200"
            >
              View All {filteredNeighborhoods.length} Neighborhoods
            </button>
          </div>
        )}

        {/* Skip Button */}
        <div className="mt-4 text-right">
          <button className="inline-flex items-center gap-2 rounded-full bg-brand-orange text-white px-4 py-2 text-sm font-semibold shadow-sm hover:bg-brand-orangeDark" onClick={onSkip}>
            Skip for now →
          </button>
        </div>
      </div>
    </Wrapper>
  );
};

export default NeighborhoodPicker;
