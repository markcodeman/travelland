import React, { useState, useEffect, useRef, Fragment } from 'react';
import ReactMarkdown from 'react-markdown';
import { Popover, Transition } from '@headlessui/react';
import VenueCard from './VenueCard';
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
  const [funFact, setFunFact] = useState(null);
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

  // Cached quick responses for common queries
  const quickResponses = {
    cafes: [
      "☕ Paris is famous for its café culture! Here are some must-visit spots:",
      "🥐 For the best croissants and coffee, try these beloved Parisian cafés:",
      "📍 Let me share some hidden gems where locals actually hang out:"
    ],
    restaurants: [
      "🍽️ Paris has incredible dining options! From bistros to fine dining:",
      "🥘 For authentic French cuisine, these restaurants are exceptional:",
      "🌟 Here are some dining spots that capture the essence of Paris:"
    ],
    museums: [
      "🎨 Paris is a paradise for art lovers! Beyond the Louvre:",
      "🖼️ The city's museums are world-class. Here are my top picks:",
      "🏛️ From classical to contemporary, Paris has it all:"
    ],
    landmarks: [
      "🗼 Paris's landmarks are iconic! Here are the must-sees:",
      "🏰 Beyond the Eiffel Tower, discover these incredible sites:",
      "📸 For the best photos and memories, visit these landmarks:"
    ],
    shopping: [
      "🛍️ Paris is a shopping paradise! From luxury to vintage:",
      "👗 For the ultimate retail therapy, explore these areas:",
      "💎 Discover unique Parisian shopping experiences:"
    ],
    nightlife: [
      "🌙 Paris comes alive after dark! Here's where to go:",
      "🍸 From chic cocktail bars to lively clubs:",
      "🎭 Experience Paris's vibrant nightlife scene:"
    ]
  };

  useEffect(() => {
    if (sessionId) localStorage.setItem('marco_session_id', sessionId);
  }, [sessionId]);

  // Keep input in sync if initialInput prop changes
  useEffect(() => {
    if (initialInput !== undefined) setInput(initialInput || '');
  }, [initialInput]);

  // Check for initial question from localStorage when component mounts
  useEffect(() => {
    const initialQuestion = localStorage.getItem('marco_initial_question');
    if (initialQuestion) {
      // Clear it so it doesn't trigger again
      localStorage.removeItem('marco_initial_question');
      // Send the message
      setTimeout(() => {
        sendMessage(initialQuestion);
      }, 500); // Small delay to let the UI settle
    }
  }, []); // Run once on mount

  // Fetch fun fact when city changes
  useEffect(() => {
    if (city && !funFact) {
      fetchFunFact();
    }
  }, [city]);

  const fetchFunFact = async () => {
    try {
      const response = await fetch('/api/fun-fact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ city })
      });
      
      if (response.ok) {
        const data = await response.json();
        setFunFact(data.funFact);
      }
    } catch (error) {
      console.error('Failed to fetch fun fact:', error);
    }
  };

  // Set initial messages when city is available
  useEffect(() => {
    if (city && messages.length === 0 && !hasSentInitial.current) {
      const initialMessage = {
        id: 'initial',
        type: 'assistant',
        content: `I found great info about ${city}! What interests you? ☕ Coffee & tea, 🚌 Transport, 💎 Hidden gems`
      };
      setMessages([initialMessage]);
      hasSentInitial.current = true;
    }
  }, [city, messages.length]); // Include category in dependencies

  const fetchVenuesForCategory = async () => {
    console.debug('fetchVenuesForCategory', { city, neighborhood, category });
    try {
      const payload = {
        query: city,
        category: category,
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
        const venueText = `I've explored ${neighborhood ? neighborhood + ', ' : ''}${city} and found some great ${category} options! Let me search for more details.`;
        // Keep existing behavior when user explicitly triggers a search
        sendMessage(venueText, `What are some great ${category} options in ${neighborhood ? neighborhood + ', ' : ''}${city}?`);
      }
    } catch (e) {
      console.error('Failed to fetch venues for category', e);
      const venueText = `I've explored ${neighborhood ? neighborhood + ', ' : ''}${city} and I'm ready to help you discover the best spots! What are you interested in - ${category}?`;
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

  async function sendMessage(text, query = null) {
    if (!text || !text.trim()) return;
    const msg = { role: 'user', text };
    setMessages(m => [...m, msg]);
    setInput('');
    setLoading(true);

    // Start with an engaging loading message
    const initialMessage = thinkingMessages[Math.floor(Math.random() * thinkingMessages.length)];
    setLoadingMessage(initialMessage);

    // Add a quick response for common queries after a short delay
    const lowerText = text.toLowerCase();
    let quickResponse = null;
    
    if (lowerText.includes('cafe') || lowerText.includes('coffee')) {
      quickResponse = quickResponses.cafes[Math.floor(Math.random() * quickResponses.cafes.length)];
    } else if (lowerText.includes('restaurant') || lowerText.includes('food') || lowerText.includes('dining')) {
      quickResponse = quickResponses.restaurants[Math.floor(Math.random() * quickResponses.restaurants.length)];
    } else if (lowerText.includes('museum') || lowerText.includes('art') || lowerText.includes('gallery')) {
      quickResponse = quickResponses.museums[Math.floor(Math.random() * quickResponses.museums.length)];
    } else if (lowerText.includes('landmark') || lowerText.includes('eiffel') || lowerText.includes('monument')) {
      quickResponse = quickResponse.landmarks[Math.floor(Math.random() * quickResponses.landmarks.length)];
    } else if (lowerText.includes('shop') || lowerText.includes('store') || lowerText.includes('boutique')) {
      quickResponse = quickResponses.shopping[Math.floor(Math.random() * quickResponses.shopping.length)];
    } else if (lowerText.includes('nightlife') || lowerText.includes('bar') || lowerText.includes('club')) {
      quickResponse = quickResponses.nightlife[Math.floor(Math.random() * quickResponses.nightlife.length)];
    }

    // Show quick response after 1.5 seconds if we have one
    if (quickResponse) {
      setTimeout(() => {
        if (loading) {
          setMessages(m => [...m, { role: 'assistant', text: quickResponse, isQuick: true }]);
          // Change loading message to indicate we're getting more details
          setLoadingMessage("Getting more detailed information...");
        }
      }, 1500);
    }

    // Cycle through different loading messages
    const messageInterval = setInterval(() => {
      if (loading) {
        const newMessage = thinkingMessages[Math.floor(Math.random() * thinkingMessages.length)];
        setLoadingMessage(newMessage);
      }
    }, 3000);

    try {
      // Use the Groq-backed chat API on the same origin (Next.js or proxied)
      const payload = {
        query: text, // Send the current message as query
        city: city,
        neighborhood: neighborhood,
        category: category,
        venues: venues,
        session_id: sessionId,
        max_results: 8
      };

      if (userLocation) {
        payload.lat = userLocation.lat;
        payload.lon = userLocation.lon;
      }

      // Always use the backend's decision logic for endpoint selection
      const response = await fetch('/api/chat/rag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();

      if (data && data.answer) {
        setMessages(m => [...m, { role: 'assistant', text: data.answer }]);
        if (data.session_id) {
          setSessionId(data.session_id);
        }
      } else {
        setMessages(m => [...m, { role: 'assistant', text: "I apologize, but I'm having trouble connecting. Please try again in a moment." }]);
        console.error('Groq API failed', data?.error);
      }
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', text: "I apologize, but I'm having trouble connecting. Please try again in a moment." }]);
      console.error('Chat API failed', e);
    } finally {
      clearInterval(messageInterval);
      setLoading(false);
      setLoadingMessage('');
    }
  }


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
              {funFact && (
                  <div style={{
                    fontSize:14, 
                    lineHeight:1.5, 
                    color: '#666', 
                    fontStyle: 'italic', 
                    marginBottom:12, 
                    padding: '8px 12px', 
                    background: 'rgba(25, 118, 210, 0.05)', 
                    borderRadius: '6px', 
                    borderLeft: '3px solid #1976d2'
                  }}>
                    💡 {funFact.replace(/Teleférico da Gaia/g, 'Teleférico de Gaia')}
                  </div>
                )}
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
                    <div className="venues-grid">
                      {msg.venues.map((venue, idx) => (
                        <VenueCard
                          key={venue.id || idx}
                          venue={{
                            ...venue,
                            city: city, // Add city for better Google Maps search
                            emoji: (venue.description || '').toLowerCase().includes('tea') ? '🫖' : (venue.description || '').toLowerCase().includes('coffee') ? '☕' : '📍',
                            sustainability: venue.tags?.includes('eco') ? '♻️' : '',
                            pricing: venue.price_level ? '💰'.repeat(venue.price_level) : ''
                          }}
                          onAddToItinerary={(v) => {
                            const newDay = {
                              date: new Date().toISOString().split('T')[0],
                              places: [v]
                            };
                            setItineraries(prev => {
                              const updated = [...prev, newDay];
                              localStorage.setItem('traveland_itineraries', JSON.stringify(updated));
                              return updated;
                            });
                            setMessages(m => [...m, {
                              role: 'assistant',
                              text: `Added **${v.name}** to your itinerary for ${newDay.date}!`
                            }]);
                          }}
                          onDirections={(v) => window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(v.address || v.name + ' ' + (v.city || ''))}`,'_blank')}
                          onMap={(v) => window.open(v.mapsUrl, '_blank')}
                          onSave={null}
                          onAskMarco={(v) => {
                            const question = `Tell me more about ${v.name}${v.description ? ' - ' + v.description : ''}. What makes it special?`;
                            setInput(question);
                            setMessages(m => [...m, { role: 'user', text: question }]);
                            handleSubmit(question);
                          }}
                        />
                      ))}
                    </div>
                  ) : (
                    // Client-side fallback card when venues array is empty or only contains summaries
                    <VenueCard key="fallback-google-maps" venue={{
                      id: 'google-maps-fallback-client',
                      name: `See more on Google Maps`,
                      address: city || '',
                      description: `No detailed venues found for ${neighborhood ? neighborhood + ', ' : ''}${city}. Explore more on Google Maps.`,
                      latitude: null,
                      longitude: null,
                      city: city || '',
                      provider: 'fallback',
                      osm_url: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(city || '')}`,
                      website: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(city || '')}`,
                      image: null,
                      emoji: '📍',
                      mapsUrl: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(city || '')}`
                    }}
                    onDirections={(v) => window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(v.address || v.name + ' ' + (v.city || ''))}`,'_blank')}
                    onMap={(v) => window.open(v.mapsUrl, '_blank')}
                    onSave={null}
                    />
                  )}
                  <div style={{marginTop:12, color:'#888'}}>What would you like to know about these places?</div>
                </div>
              ) : msg.role === 'assistant' ? (
                <div>
                  {/* Condensed handling for generic Google Maps fallback text */}
                  {isGoogleMapsFallback(msg.text) ? (
                    <div className="venue-message" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ fontWeight: 700, marginBottom: 6 }}>{firstSentences(msg.text, 1)}</div>
                      <VenueCard key="fallback-google-maps-short" venue={{
                        id: 'google-maps-fallback-client',
                        name: `See more on Google Maps`,
                        address: city || '',
                        description: `No venues found, but you can explore more options on Google Maps for ${neighborhood ? neighborhood + ', ' : ''}${city}.`,
                        latitude: null,
                        longitude: null,
                        city: city || '',
                        provider: 'fallback',
                        osm_url: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(neighborhood ? neighborhood + ', ' + city : city || '')}`,
                        website: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(neighborhood ? neighborhood + ', ' + city : city || '')}`,
                        image: null,
                        emoji: '📍',
                        mapsUrl: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(neighborhood ? neighborhood + ', ' + city : city || '')}`
                      }}
                      onDirections={(v) => window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(v.address || v.name + ' ' + (v.city || ''))}`,'_blank')}
                      onMap={(v) => window.open(v.mapsUrl, '_blank')}
                      onSave={null}
                      />
                      <div style={{ color: '#666' }}>Tip: try toggling <strong>Local Gems Only</strong> or selecting a nearby neighborhood for better local results.</div>
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
                        {msg.text}
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
                            if (name) items.push(`${name}. ${description}`);
                          }
                        }
                        // If still no items, fallback to Google Maps
                        if (items.length === 0) {
                          items.push(`See more on Google Maps`);
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
                              else if (/(beach|platja)/i.test(lower)) {
                                emoji = '🏖️';
                                tags = 'natural=beach';
                                category = 'beach';
                              }
                              
                              // Generate a Google Maps search URL using name and city
                              const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name + (city ? ' ' + city : ''))}`;
                              return (
                                <VenueCard
                                  key={idx}
                                  venue={{
                                    name,
                                    description,
                                    emoji,
                                    tags,
                                    category,
                                    city: city || '',
                                    provider: '',
                                    mapsUrl,
                                  }}
                                />
                              );
                            })}
                          </div>
                        );
                      })()}
                    </>
                  )}
                </div>
              ) : (
                msg.text
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
