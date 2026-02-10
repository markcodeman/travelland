
import ReactMarkdown from 'react-markdown';

export default function QuickGuide({ guide, images, source, source_url }) {
  if (!guide) return null;
  
  let formattedGuide;
  const isList = guide.includes('\n- ') || guide.includes('\n• ');
  
  if (guide.includes('\n') || guide.includes('**')) {
    formattedGuide = <ReactMarkdown>{guide}</ReactMarkdown>;
  } else if (isList) {
    const lines = guide.split(/\n|\r/).filter(l => l.trim());
    formattedGuide = (
      <ul style={{fontSize: '1.13em', lineHeight: 1.7, paddingLeft: 24}}>
        {lines.map((line, i) => {
          let content = line.trim();
          return <li key={i} style={{marginBottom: '0.5em'}}>• {content}</li>;
        })}
      </ul>
    );
  } else {
    const KEYWORD_EMOJIS = [
      { emoji: "🌸", keywords: ["cherry blossom", "sakura", "桜", "さくら"] },
      { emoji: "🏰", keywords: ["palace", "castle", "fortress", "城", "お城"] },
      { emoji: "🗼", keywords: ["Tokyo", "skyscraper", "tower", "東京", "タワー", "塔"] },
      { emoji: "🏛️", keywords: ["Rome", "ancient", "roman"] },
      { emoji: "🗽", keywords: ["York", "Manhattan"] },
      { emoji: "⛪", keywords: ["vatican", "cathedral", "教会", "教堂"] },
      { emoji: "⛲", keywords: ["fountain", "trevi", "噴水"] },
      { emoji: "🎨", keywords: ["gallery", "museum", "art", "美術館", "博物館", "芸術"] },
      { emoji: "🌳", keywords: ["park", "garden", "nature", "公園", "庭", "自然"] },
      { emoji: "🛍️", keywords: ["market", "shopping", "買い物", "ショッピング", "市場"] },
      { emoji: "🌊", keywords: ["ocean", "sea", "coast", "海", "海岸", "浜辺"] },
      { emoji: "🏔️", keywords: ["mountain", "hill", "山", "丘"] },
      { emoji: "🍝", keywords: ["food", "restaurant", "料理", "食べ物", "レストラン"] },
      { emoji: "🎭", keywords: ["theater", "theatre", "劇場", "演劇"] },
      { emoji: "🎪", keywords: ["festival", "event", "祭り", "祭", "イベント"] },
    ];
    
    function injectEmojis(text, globalUsedEmojis) {
      const parts = [];
      const keywordList = KEYWORD_EMOJIS.flatMap(e => e.keywords.map(k => ({ keyword: k, emoji: e.emoji })));
      const matches = [];
      
      // Find all matches (whole word matches only)
      keywordList.forEach(({ keyword, emoji }) => {
        const lowerKeyword = keyword.toLowerCase();
        
        // Split by whitespace and punctuation to find whole words
        const tokens = text.split(/(\s+|[.,!?;:])/);
        let pos = 0;
        tokens.forEach(token => {
          // Check if token matches keyword (case insensitive, ignoring trailing punctuation)
          const cleanToken = token.toLowerCase().replace(/[.,!?;:]+$/, '');
          if (cleanToken === lowerKeyword) {
            matches.push({ start: pos, end: pos + token.length, emoji });
          }
          pos += token.length;
        });
      });
      
      // Sort by start position and remove overlapping matches
      matches.sort((a, b) => a.start - b.start);
      const filtered = [];
      let lastEnd = -1;
      matches.forEach(m => {
        if (m.start >= lastEnd) {
          filtered.push(m);
          lastEnd = m.end;
        }
      });
      
      // Build result with emoji prefix (only once per emoji type globally)
      let lastIdx = 0;
      filtered.forEach(({ start, end, emoji }) => {
        // Extract the matched word and any trailing punctuation
        const fullMatch = text.slice(start, end);
        const trailingPunct = fullMatch.match(/[.,!?;:]+$/);
        const wordOnly = trailingPunct ? fullMatch.slice(0, -trailingPunct[0].length) : fullMatch;
        const actualEnd = start + wordOnly.length;
        
        if (globalUsedEmojis.has(emoji)) {
          // Emoji already used globally, just add the text
          if (start > lastIdx) {
            parts.push(text.slice(lastIdx, end));
          } else {
            parts.push(fullMatch);
          }
          lastIdx = end;
        } else {
          // First occurrence of this emoji - prefix with emoji (before punctuation)
          globalUsedEmojis.add(emoji);
          if (start > lastIdx) {
            parts.push(text.slice(lastIdx, start));
          }
          parts.push(emoji, wordOnly);
          if (trailingPunct) {
            parts.push(trailingPunct[0]);
          }
          lastIdx = end;
        }
      });
      if (lastIdx < text.length) {
        parts.push(text.slice(lastIdx));
      }
      return parts;
    }
    
    const sentences = guide.split(/(?<=[.!?])\s+(?=[A-Z])/g);
    // Track emojis globally across all sentences to prevent duplicates
    const globalUsedEmojis = new Set();
    
    formattedGuide = sentences.map((s, i) => {
      const parts = injectEmojis(s.trim(), globalUsedEmojis);
      return (
        <p key={i} style={{marginBottom: '0.7em', fontSize: '1.13em', lineHeight: 1.7}}>
          {parts}
        </p>
      );
    });
  }
  
  return (
    <div className="quick-guide">
      <div className="quick-guide-content" style={{fontSize: '1.13em', lineHeight: 1.7, color: '#222'}}>
        {formattedGuide}
      </div>
      {source && (
        <div className="quick-source" style={{marginTop: 8, fontSize: '0.97em', color: '#666'}}>
          Source: {source_url ? (
            <a href={source_url} target="_blank" rel="noopener noreferrer">{source}</a>
          ) : source}
        </div>
      )}
      {images && images.length > 0 && (
        <div className="quick-images">
          {images.map((img, i) => (
            <img key={i} src={img.url || img} alt="" className="quick-image" />
          ))}
        </div>
      )}
    </div>
  );
}
