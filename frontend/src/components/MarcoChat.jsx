import { Popover, Transition } from '@headlessui/react';
import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './MarcoChat.css';

export default function MarcoChat({ city, neighborhood, venues, category, initialInput, onClose, results, wikivoyage }) {
  const [messages, setMessages] = useState([]);
  const [itineraries, setItineraries] = useState(() => {
    const saved = localStorage.getItem('traveland_itineraries');
    return saved ? JSON.parse(saved) : [];
  });
  const [input, setInput] = useState(initialInput || ''); // allow initial input
  const [sessionId, setSessionId] = useState(localStorage.getItem('marco_session_id') || null);
  const [loading, setLoading] = useState(false);
  const [userLocation, setUserLocation] = useState(null);
  const [loadingMessage, setLoadingMessage] = useState('');
  const messagesEndRef = useRef(null);
  const hasSentInitial = useRef(false);

  // Engaging loading messages
  const thinkingMessages = [
    "Hmmm, let me think about that...",
    "Searching my travel knowledge...",
    "Consulting my local guides...",
    "Finding the best recommendations...",
    "Checking my travel notes...",
    "Exploring possibilities for you...",
    "Digging into my travel database...",
    "Crafting the perfect response..."
  ];

  // Cached quick responses for common queries (neutral, city-aware templates)
  const quickResponses = {
    cafes: [
      "☕ I can find the best cafés in {city} — searching local favorites now...",
      "☕ Looking up coffee spots in {city} — stand by while I pull top picks..."
    ],
    restaurants: [
      "🍽️ I can find top restaurants in {city} — searching now...",
      "🍽️ Looking up popular dining spots in {city} — one moment..."
    ],
    museums: [
      "🎨 I can find notable museums and galleries in {city} — fetching highlights...",
      "🎨 Looking up art and cultural spots in {city} — stand by..."
    ],
    landmarks: [
      "🏛️ I can find iconic landmarks and architecture in {city} — fetching...",
      "📸 Finding the best sights and monuments in {city} — one moment..."
    ],
    shopping: [
      "🛍️ Searching for shopping districts and unique stores in {city}...",
      "🛍️ Looking up local markets and boutiques in {city} — stand by..."
    ],
    nightlife: [
      "🌙 Searching for bars and nightlife spots in {city} — fetching live results...",
      "🌙 Looking up late-night options and cocktail bars in {city} — one moment..."
    ],
    parks: [
      "🌳 Finding beautiful parks and gardens in {city}...",
      "🌿 Looking up outdoor spaces and nature spots in {city} — stand by..."
    ],
    hotels: [
      "🏨 Searching for accommodations in {city}...",
      "🏨 Finding great places to stay in {city} — one moment..."
    ]
  };

  useEffect(() => {
    if (sessionId) localStorage.setItem('marco_session_id', sessionId);
  }, [sessionId]);

  // Context-aware loading messages
  const getContextualLoadingMessage = (query) => {
    const lower = query.toLowerCase();
    if (lower.includes('coffee') || lower.includes('cafe')) return `Finding the best cafés in ${city}...`;
    if (lower.includes('restaurant') || lower.includes('food')) return `Searching for top dining spots in ${city}...`;
    if (lower.includes('museum') || lower.includes('art')) return `Looking up cultural highlights in ${city}...`;
    if (lower.includes('architecture') || lower.includes('design') || lower.includes('landmark') || lower.includes('heritage') || lower.includes('maritime') || lower.includes('history')) return `Finding iconic architecture and heritage in ${city}...`;
    if (lower.includes('park') || lower.includes('garden')) return `Searching for parks and outdoor spaces in ${city}...`;
    if (lower.includes('hotel') || lower.includes('stay')) return `Finding accommodations in ${city}...`;
    return thinkingMessages[Math.floor(Math.random() * thinkingMessages.length)];
  };

  // Generate smart suggestions based on conversation context
  const generateSuggestions = (lastMessage) => {
    if (!city) return [];
    
    const baseSuggestions = [
      `Best ${category || 'places'} in ${city}`,
      'Hidden local gems',
      'How to get around',
      'What to avoid'
    ];
    
    if (neighborhood) {
      baseSuggestions.push(`More about ${neighborhood}`);
    }
    
    // Add context-aware suggestions based on last message
    if (lastMessage?.text) {
      const text = lastMessage.text.toLowerCase();
      if (text.includes('cafe') || text.includes('coffee')) {
        return ['☕ Best coffee', '🥐 Great pastries', '💻 Work-friendly spots', ...baseSuggestions];
      }
      if (text.includes('restaurant') || text.includes('food')) {
        return ['🍽️ Local specialties', '💰 Budget options', '🌱 Vegetarian', ...baseSuggestions];
      }
      if (text.includes('museum') || text.includes('art') || text.includes('gallery') || text.includes('architecture') || text.includes('design')) {
        return ['🏛️ Must-see museums', '🎨 Architecture tours', '🎭 Art walks', ...baseSuggestions];
      }
    }
    
    return baseSuggestions;
  };

  const sendMessage = useCallback(async (text, query = null) => {
    if (!text || !text.trim()) return;
    const msg = { role: 'user', text };
    setMessages(m => [...m, msg]);
    setInput('');
    setLoading(true);

    // Use contextual loading message
    setLoadingMessage(getContextualLoadingMessage(text));

    // Add a quick response for common queries after a short delay
    const lowerText = text.toLowerCase();
    let quickResponse = null;
    
    // Detect a category match - ONLY for explicit venue-seeking queries
    // Topic queries like "heritage", "maritime", "history" should fall through to RAG
    let matchedCategory = null;
    if (lowerText.includes('cafe') || lowerText.includes('coffee') || lowerText.includes('espresso')) {
      matchedCategory = 'cafes';
    } else if (lowerText.includes('restaurant') || lowerText.includes('food') || lowerText.includes('dining') || lowerText.includes('eat')) {
      matchedCategory = 'restaurants';
    } else if (lowerText.includes('museum') || lowerText.includes('art gallery') || lowerText.includes('exhibition')) {
      matchedCategory = 'museums';
    } else if (lowerText.includes('nightlife') || lowerText.includes('bar') || lowerText.includes('club') || lowerText.includes('pub')) {
      matchedCategory = 'nightlife';
    } else if (lowerText.includes('park') || lowerText.includes('garden') || lowerText.includes('nature')) {
      matchedCategory = 'parks';
    } else if (lowerText.includes('hotel') || lowerText.includes('stay') || lowerText.includes('accommodation')) {
      matchedCategory = 'hotels';
    }
    // Note: heritage, maritime, history, architecture, etc. are NOT here - they go to RAG

    if (matchedCategory) {
      // Use a neutral, city-aware quick message while we fetch venues
      const templates = quickResponses[matchedCategory] || [`Searching for ${matchedCategory} in ${city}...`];
      const tmpl = templates.length ? templates[Math.floor(Math.random() * templates.length)] : `Searching for ${matchedCategory} in ${city}...`;
      const quickMsg = tmpl.replace('{city}', city || 'this city');
      setMessages(m => [...m, { role: 'assistant', text: quickMsg, isQuick: true }]);

      // Ask the client to fetch venues for the matched category (override allowed)
      fetchVenuesForCategory(matchedCategory);
      return;
    }

    try {
      // Build conversation history from messages (exclude initial message and venue cards)
      const history = messages
        .filter(m => m.role && (m.role === 'user' || m.role === 'assistant') && m.text)
        .slice(-6) // Last 6 messages for context
        .map(m => ({ role: m.role, content: m.text }));
      
      // Use the RAG chat endpoint
      const payload = {
        query: text,
        city: city,
        neighborhood: neighborhood,
        category: category,
        venues: [],
        history: history, // Send conversation history
        max_results: 8
      };

      const response = await fetch('/api/chat/rag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error('Chat request failed');
      }

      const data = await response.json();
      const assistantMessage = data.answer || data.response || 'I apologize, but I encountered an issue processing your request.';
      
      // Generate contextual suggestions based on the response
      const suggestions = generateSuggestions({ text: assistantMessage });

      setMessages(m => [...m, { 
        role: 'assistant', 
        text: assistantMessage,
        suggestions: suggestions.slice(0, 4) // Add top 4 suggestions
      }]);
      
      // Update session ID if provided
      if (data.session_id) {
        setSessionId(data.session_id);
      }
    } catch (error) {
      console.error('Chat error:', error);
      const errorMsg = { 
        role: 'assistant', 
        text: `I'm having trouble connecting right now. This could be a network issue or the server might be busy.`,
        isError: true,
        retryText: text, // Store original text for retry
        suggestions: ['🔄 Try again', '💬 Ask something else', '📍 Show me venues']
      };
      setMessages(m => [...m, errorMsg]);
    } finally {
      setLoading(false);
    }
  }, [city, neighborhood, category, sessionId, thinkingMessages, quickResponses, generateSuggestions]);

  // Auto-send initialInput if provided
  useEffect(() => {
    if (initialInput && initialInput.trim() && !hasSentInitial.current) {
      hasSentInitial.current = true;
      // Send the message automatically after a short delay
      setTimeout(() => {
        sendMessage(initialInput);
      }, 800); // Let UI settle first
    }
  }, [initialInput, sendMessage]);

  

  // Set initial messages when city is available
  useEffect(() => {
    if (city && messages.length === 0 && !hasSentInitial.current) {
      const initialMessage = {
        role: 'assistant',
        text: `I found great info about ${city}! What interests you?`,
        suggestions: ['☕ Coffee & tea', '🚌 Transport', '💎 Hidden gems', '🍽️ Local food']
      };
      setMessages([initialMessage]);
      hasSentInitial.current = true;
    }
  }, [city, messages.length]);

  const fetchVenuesForCategory = async (overrideCategory = null) => {
    const useCategory = overrideCategory || category;
    console.debug('fetchVenuesForCategory', { city, neighborhood, category: useCategory });
    try {
      const payload = {
        query: city,
        category: useCategory,
        neighborhood: neighborhood,
      };
      const resp = await fetch('/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      const fetchedVenues = (data.venues || []).filter(v => v.provider !== 'wikivoyage');
      console.log('Fetched venues:', fetchedVenues.length, fetchedVenues.slice(0, 3));
      
      if (fetchedVenues.length > 0) {
        // Use REAL venue data from backend
        setMessages([{ role: 'assistant', venues: fetchedVenues.slice(0, 10) }]);
      } else {
        const venueText = `I've explored ${neighborhood ? neighborhood + ', ' : ''}${city} and found some great ${useCategory} options! Let me search for more details.`;
        // Keep existing behavior when user explicitly triggers a search
        sendMessage(venueText, `What are some great ${useCategory} options in ${neighborhood ? neighborhood + ', ' : ''}${city}?`);
      }
    } catch (e) {
      console.error('Failed to fetch venues for category', e);
      const venueText = `I've explored ${neighborhood ? neighborhood + ', ' : ''}${city} and I'm ready to help you discover the best spots! What are you interested in - ${useCategory}?`;
      sendMessage(venueText);
    }
  };

  const handleUseLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setUserLocation({
            lat: position.coords.latitude,
            lon: position.coords.longitude
          });
        },
        (error) => {
          console.error("Geolocation error", error);
        }
      );
    }
  };

  

  // Helpers for rendering assistant fallback text
  const isGoogleMapsFallback = (text) => /no venues found|see more on google maps|explore more options on google maps|no detailed venues found/i.test(text || '');
  const firstSentences = (text, n = 2) => (text || '').split(/(?<=[.?!])\s+/).slice(0, n).join(' ');

  // Submit handler for the chat input
  const handleSubmit = () => {
    console.debug('handleSubmit', { category, input, loading });
    if (!input.trim() || loading) return;
    // If there's a category and input matches the category, fetch venues instead of AI chat
    if (category && input.trim().toLowerCase().includes(category.toLowerCase())) {
      console.debug('handleSubmit -> fetching venues for category', category);
      fetchVenuesForCategory();
      return;
    }
    sendMessage(input);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Helper to convert text with place names to Google Maps links
  const addGoogleMapsLinks = (text) => {
    if (!text || !city) return text;
    
    // First, match explicit bold/numbered patterns like "**Place Name**" or "1. Place Name" or "- Place Name"
    const explicitRegex = /(\*\*[\w\s&.'ʼ,()éèêëàâäôöùûüçÉÈÊËÀÂÄÔÖÙÛÜÇ\-]{2,50}\*\*|\d+\.\s+[\w\s&.'ʼ,()éèêëàâäôöùûüçÉÈÊËÀÂÄÔÖÙÛÜÇ\-]{2,50}|-\s+[\w\s&.'ʼ,()éèêëàâäôöùûüçÉÈÊËÀÂÄÔÖÙÛÜÇ\-]{2,50})/g;
    
    text = text.replace(explicitRegex, (match) => {
      // Check if match is already a markdown link
      if (match.includes('](')) return match;
      
      const placeName = match.replace(/^\*\*|\*\*$/g, '').replace(/^\d+\.\s*|^-\s*/, '').trim();
      if (!placeName || placeName.length < 2 || placeName.length > 50) return match;
      
      const searchQuery = encodeURIComponent(`${placeName}, ${neighborhood ? neighborhood + ', ' : ''}${city}`);
      const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${searchQuery}`;
      
      return `[${match}](${mapsUrl})`;
    });
    
    // Second, match capitalized proper nouns that look like place names
    // Match patterns like "The Place Name" or "École de Something" followed by comma, period, or end of line
    const properNounRegex = /\b(The\s+[A-Z][\w\s&.'ʼ-]+?(?:Building|Campus|School|Institute|Center|Centre|Park|Garden|Tower|Bridge|Square|Street|Avenue|Boulevard|Cathedral|Basilica|Museum|Gallery|Theatre|Palace|Castle|Market|Harbor|Port|Beach|Café|Restaurant|Hotel|Hotel|Luminy|Marseille)|[A-ZÁÉÍÓÚÑ][\w\s&.'ʼ-]*(?:École|Université|Institut|Campus|Hexagon|Vieux-Port|Calanques|Notre-Dame))\b/g;
    
    text = text.replace(properNounRegex, (match) => {
      // Avoid double-linking if already linked
      if (match.includes('](')) return match;
      const placeName = match.trim();
      if (!placeName || placeName.length < 3 || placeName.length > 60) return match;
      
      // REJECT matches that contain ' or ' or ' and ' - these are clarifying questions, not place names
      if (/\s+or\s+|\s+and\s+/i.test(placeName)) return match;
      
      const searchQuery = encodeURIComponent(`${placeName}, ${city}`);
      const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${searchQuery}`;
      
      return `[${placeName}](${mapsUrl})`;
    });
    
    return text;
  };

  return (
    <div className="marco-modal-overlay">
      <div className="marco-modal">
        <div className="marco-header">
          <span>Marco — Travel Assistant for {neighborhood ? `${neighborhood}, ` : ''}{city}</span>
          <button className="marco-close" onClick={onClose}>×</button>
        </div>

        <div className="marco-messages" role="region" aria-live="polite">
          {/* City guide as first message */}
          <div className="marco-msg assistant">
            <div className="city-guide">
              <div style={{fontWeight:600, marginBottom:8}}>📍 {city} Travel Guide</div>
              {results?.quick_guide ? (
                <div style={{fontSize:14, lineHeight:1.5, color: '#333'}}>
                  <ReactMarkdown
                    components={{
                      a: props => <a {...props} target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2', textDecoration: 'underline' }}>{props.children}</a>,
                      strong: props => <strong style={{ color: '#333' }}>{props.children}</strong>,
                      p: props => <p style={{ marginBottom: '16px', lineHeight: '1.6' }}>{props.children}</p>
                    }}
                  >
                    {results.quick_guide}
                  </ReactMarkdown>
                </div>
              ) : (
                <div style={{fontSize:14, color: '#666'}}>
                  No city guide information available for {city}.
                </div>
              )}
              {results?.source && (
                <div style={{fontSize:12, color: '#666', marginTop:8}}>
                  Source: {results.source}{results.source_url && (
                    <a href={results.source_url} target="_blank" rel="noopener noreferrer" style={{color: '#1976d2', marginLeft: '4px'}}>↗</a>
                  )}
                </div>
              )}
            </div>
          </div>
          {messages.map((msg, i) => (
            <div key={i} className={`marco-msg ${msg.role} ${msg.isQuick ? 'quick-response' : ''}`}>
              {msg.role === 'assistant' && msg.venues ? (
                <div className="venue-message">
                  <div style={{fontWeight:700, fontSize:'1.1em', marginBottom:16}}>☕ Here are some great places I found:</div>
                  {msg.venues && msg.venues.length > 0 ? (
                    <div className="venues-list" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {msg.venues.map((venue, idx) => {
                        const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venue.name + ' ' + (city || ''))}`;
                        return (
                          <div key={venue.id || idx} style={{
                            background: 'white',
                            borderRadius: '8px',
                            padding: '12px 16px',
                            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                          }}>
                            <div>
                              <h4 style={{ margin: '0 0 4px 0', fontSize: '16px', fontWeight: '600' }}>
                                {venue.name}
                              </h4>
                              {venue.address && (
                                <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>
                                  {venue.address}
                                </p>
                              )}
                            </div>
                            <a
                              href={mapsUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                background: '#4285f4',
                                color: 'white',
                                padding: '8px 12px',
                                borderRadius: '6px',
                                textDecoration: 'none',
                                fontSize: '14px',
                                fontWeight: '500'
                              }}
                            >
                              📍 Maps
                            </a>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    // Client-side fallback when no venues found
                    <div style={{
                      background: 'white',
                      borderRadius: '8px',
                      padding: '16px',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                      textAlign: 'center'
                    }}>
                      <p style={{ margin: '0 0 12px 0', color: '#666' }}>
                        No detailed venues found for {neighborhood ? neighborhood + ', ' : ''}{city}. Explore more on Google Maps.
                      </p>
                      <a
                        href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(category + ' ' + (city || ''))}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          background: '#4285f4',
                          color: 'white',
                          padding: '10px 16px',
                          borderRadius: '6px',
                          textDecoration: 'none',
                          fontSize: '14px',
                          fontWeight: '500',
                          display: 'inline-block'
                        }}
                      >
                        📍 Search on Google Maps
                      </a>
                    </div>
                  )}
                  <div style={{marginTop:12, color:'#888'}}>What would you like to know about these places?</div>
                </div>
              ) : msg.role === 'assistant' ? (
                <div>
                  {/* Condensed handling for generic Google Maps fallback text */}
                  {isGoogleMapsFallback(msg.text) ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ fontWeight: 700, marginBottom: 6 }}>{firstSentences(msg.text, 1)}</div>
                      <div style={{
                        background: 'white',
                        borderRadius: '8px',
                        padding: '16px',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                        textAlign: 'center'
                      }}>
                        <p style={{ margin: '0 0 12px 0', color: '#666' }}>
                          No venues found, but you can explore more options on Google Maps for {neighborhood ? neighborhood + ', ' : ''}{city}.
                        </p>
                        <a
                          href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(neighborhood ? neighborhood + ', ' + city : city || '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            background: '#4285f4',
                            color: 'white',
                            padding: '10px 16px',
                            borderRadius: '6px',
                            textDecoration: 'none',
                            fontSize: '14px',
                            fontWeight: '500',
                            display: 'inline-block'
                          }}
                        >
                          📍 Search on Google Maps
                        </a>
                      </div>
                    </div>
                  ) : (
                    <>
                      <ReactMarkdown
                        components={{
                          a: props => <a {...props} target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2', textDecoration: 'underline', fontWeight: 600 }}>{props.children}</a>,
                          strong: props => <strong style={{ color: '#333', fontWeight: 700 }}>{props.children}</strong>,
                          p: props => <p style={{ marginBottom: '16px', lineHeight: '1.6' }}>{props.children}</p>,
                          li: props => <li style={{ marginBottom: 6 }}>{props.children}</li>,
                          small: props => <small style={{ color: '#888', fontSize: '0.95em' }}>{props.children}</small>,
                          span: props => <span style={{ color: '#1976d2', fontWeight: 600 }}>{props.children}</span>
                        }}
                        skipHtml={false}
                        disallowedElements={[]}
                        allowElement={() => true}
                      >
                        {addGoogleMapsLinks(msg.text)}
                      </ReactMarkdown>

                      {/* If the assistant returned a summary/list (wikivoyage-style) and no venues were provided,
                          parse the list and render each as a VenueCard for a richer UI. */}
                      {(() => {
                        const text = msg.text || '';
                        const looksLikeList = /\n\s*\d+\.|^\s*[-•*]\s+/m.test(text) || /here are (a few|some) recommendations/i.test(text);
                        let items = [];
                        if (looksLikeList) {
                          // Extract list items from markdown-like text
                          const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
                          const bulletRe = /^[-•*]\s+(.*)$/;
                          const numberedRe = /^\d+\.\s+\*\*(.+?)\*\*:?\s*(.*)$/; // Fixed to handle **Bold**: format
                          for (const line of lines) {
                            let m = line.match(bulletRe) || line.match(numberedRe);
                            if (m) {
                              const name = m[1] ? m[1].trim() : '';
                              const desc = m[2] ? m[2].trim() : '';
                              if (name) {
                                items.push(desc ? `${name}. ${desc}` : name);
                              }
                            }
                          }
                          if (items.length === 0) {
                            const afterHeader = text.split(/here are|here's|my top picks/i)[1];
                            if (afterHeader) {
                              for (const part of afterHeader.split(/\n|;|,|\.|\|/)) {
                                const t = part.replace(/^\s*[-•*\d\.]+\s*/, '').trim();
                                if (t) items.push(t);
                              }
                            }
                          }
                        }
                        // If no items found, try to extract venues from paragraphs using regex
                        if (items.length === 0) {
                          // Regex for patterns like: 'I recommend visiting [Venue], ...', 'Another great option is [Venue], ...', etc.
                          const paraRegex = /(?:I recommend visiting|Another great option is|You might enjoy|If you're looking for|One popular spot is|A great option is|Try|Check out|Visit|For a traditional.*?try|For a more modern.*?try|You might like)\s+([A-ZÁÉÍÓÚÑ][\w\s'’&-]+?)(?:,|\.|\-|:|\s)([^.\n]*)/gi;
                          let match;
                          while ((match = paraRegex.exec(text)) !== null) {
                            const name = match[1].trim();
                            const description = match[2].trim();
                            // Reject articles and short words as venue names
                            const articles = ['the', 'a', 'an', 'this', 'that', 'these', 'those', 'my', 'your', 'his', 'her'];
                            // Also reject names containing ' or ' or ' and ' - these are clarifying questions
                            if (name && !articles.includes(name.toLowerCase()) && name.length > 3 && !/\s+or\s+|\s+and\s+/i.test(name)) {
                              items.push(`${name}. ${description}`);
                            }
                          }
                        }
                        // If still no items, just return the original text without adding Google Maps fallback
                        if (items.length === 0) {
                          return (
                            <div style={{marginTop: 12, color: '#666'}}>
                              <strong>No venues found in this area.</strong>
                            </div>
                          );
                        }
                        // Try to parse name/description pairs for richer cards
                        return (
                          <div className="venue-message flex flex-col gap-2 mt-3 mb-2">
                            {items.map((item, idx) => {
                              // Try to split into name and description
                              let [name, ...descParts] = item.split(/\*\*|\.|\:|\-/);
                              name = name.trim();
                              const description = descParts.join('.').trim();
                              // Heuristic emoji selection and category detection
                              const lower = name.toLowerCase();
                              let emoji = '📍';
                              let tags = '';
                              let category = '';
                              
                              if (/(coffee|cafe|espresso|latte|tea)/i.test(lower)) {
                                emoji = '☕';
                                tags = 'amenity=cafe,cuisine=coffee';
                                category = 'cafe';
                              }
                              else if (/(museum|museu|gallery|historic|cathedral|monument)/i.test(lower)) {
                                emoji = '🏛️';
                                tags = 'tourism=museum';
                                category = 'museum';
                              }
                              else if (/(park|parc|garden|jardins|outdoor)/i.test(lower)) {
                                emoji = '🌳';
                                tags = 'leisure=park';
                                category = 'park';
                              }
                              else if (/(bar|pub|cocktail|wine|beer)/i.test(lower)) {
                                emoji = '🍸';
                                tags = 'amenity=bar';
                                category = 'bar';
                              }
                              else if (/(restaurant|food|dining)/i.test(lower)) {
                                emoji = '🍽️';
                                tags = 'amenity=restaurant';
                                category = 'restaurant';
                              }
                              else if (/(hotel|accommodation)/i.test(lower)) {
                                emoji = '🏨';
                                tags = 'tourism=hotel';
                                category = 'hotel';
                              }
                              else if (/(shop|store|mall)/i.test(lower)) {
                                emoji = '🛍️';
                                tags = 'shop=retail';
                                category = 'shop';
                              }
                              else if (/(architecture|design|building|modernisme|gaudi|sagrada)/i.test(lower)) {
                                emoji = '�️';
                                tags = 'tourism=attraction,architectural';
                                category = 'architecture';
                              }
                              
                              // Generate a Google Maps search URL using name and city
                              const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name + (city ? ' ' + city : ''))}`;
                              return (
                                <div key={idx} style={{
                                  background: 'white',
                                  borderRadius: '8px',
                                  padding: '12px 16px',
                                  boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  marginBottom: '8px'
                                }}>
                                  <div>
                                    <h4 style={{ margin: '0 0 4px 0', fontSize: '16px', fontWeight: '600' }}>
                                      {emoji} {name}
                                    </h4>
                                    {description && (
                                      <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>
                                        {description}
                                      </p>
                                    )}
                                  </div>
                                  <a
                                    href={mapsUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                      background: '#4285f4',
                                      color: 'white',
                                      padding: '8px 12px',
                                      borderRadius: '6px',
                                      textDecoration: 'none',
                                      fontSize: '14px',
                                      fontWeight: '500'
                                    }}
                                  >
                                    📍 Maps
                                  </a>
                                </div>
                              );
                            })}
                          </div>
                        );
                      })()}
                    </>
                  )}
                </div>
              ) : (
                <div>
                  {msg.isError ? (
                    <div className="error-message">
                      <div>{msg.text}</div>
                      {msg.retryText && (
                        <button 
                          className="retry-btn"
                          onClick={() => sendMessage(msg.retryText)}
                          disabled={loading}
                        >
                          🔄 Try Again
                        </button>
                      )}
                    </div>
                  ) : (
                    msg.text
                  )}
                </div>
              )}
              
              {/* Suggestion chips for quick replies */}
              {msg.role === 'assistant' && msg.suggestions && msg.suggestions.length > 0 && (
                <div className="suggestion-chips">
                  {msg.suggestions.map((suggestion, idx) => (
                    <button
                      key={idx}
                      className="suggestion-chip"
                      onClick={() => sendMessage(suggestion)}
                      disabled={loading}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="marco-msg assistant">
              <div className="loading-message">
                <div className="thinking-emoji">🤔</div>
                <div className="thinking-text">{loadingMessage || "Thinking..."}</div>
                <div className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="marco-input" role="form" aria-label="Marco chat input">
          {itineraries.length > 0 && (
            <Popover className="itinerary-popover">
              <Popover.Button className="itinerary-button">
                🗓️ My Plan ({itineraries.reduce((acc, curr) => acc + curr.places.length, 0)})
              </Popover.Button>
              <Transition
                as={Fragment}
                enter="transition ease-out duration-200"
                enterFrom="opacity-0 translate-y-1"
                enterTo="opacity-100 translate-y-0"
                leave="transition ease-in duration-150"
                leaveFrom="opacity-100 translate-y-0"
                leaveTo="opacity-0 translate-y-1"
              >
                <Popover.Panel className="itinerary-panel">
                  <div className="panel-header">
                    <h3>Travel Itinerary</h3>
                    <button onClick={() => setItineraries([])}>Clear All</button>
                  </div>
                  {itineraries.map((day, i) => (
                    <div key={i} className="day-group">
                      <h4>Day {i+1} - {day.date}</h4>
                      <div className="day-places">
                        {day.places.map((place, j) => (
                          <div key={j} className="place-item">
                            <span>{place.emoji || '📍'}</span>
                            <div>
                              <strong>{place.name}</strong>
                              <small>{place.address}</small>
                            </div>
                            <button 
                              onClick={() => {
                                const updated = [...itineraries];
                                updated[i].places.splice(j, 1);
                                if(updated[i].places.length === 0) updated.splice(i, 1);
                                setItineraries(updated);
                                localStorage.setItem('traveland_itineraries', JSON.stringify(updated));
                              }}
                            >✕</button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </Popover.Panel>
              </Transition>
            </Popover>
          )}
          <button onClick={handleUseLocation}>Use my location</button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about restaurants, attractions, travel tips..."
            disabled={loading}
          />
          <button
            onClick={() => {
              if (category && !input.trim()) {
                fetchVenuesForCategory();
              } else {
                handleSubmit();
              }
            }}
            disabled={loading || (!input.trim() && !category)}
          >
            {loading ? '...' : "Let's Go"}
          </button>
        </div>
      </div>
    </div>
  );
}
