import React, { useState, useEffect, useRef, Fragment } from 'react';
import ReactMarkdown from 'react-markdown';
import { Popover, Transition } from '@headlessui/react';
import VenueCard from './VenueCard';
import './MarcoChat.css';

export default function MarcoChat({ city, neighborhood, venues, category, initialInput, onClose }) {
  const [messages, setMessages] = useState([]);
  const [itineraries, setItineraries] = useState(() => {
    const saved = localStorage.getItem('traveland_itineraries');
    return saved ? JSON.parse(saved) : [];
  });
  const [input, setInput] = useState(initialInput || ''); // allow initial input
  const [sessionId, setSessionId] = useState(localStorage.getItem('marco_session_id') || null);
  const [loading, setLoading] = useState(false);
  const [requestLimitReached, setRequestLimitReached] = useState(false);
  const [requestsRemaining, setRequestsRemaining] = useState(1);
  const messagesEndRef = useRef(null);
  const hasSentInitial = useRef(false);

  useEffect(() => {
    if (sessionId) localStorage.setItem('marco_session_id', sessionId);
  }, [sessionId]);

  // Keep input in sync if initialInput prop changes
  useEffect(() => {
    if (initialInput !== undefined) setInput(initialInput || '');
  }, [initialInput]);

  // Auto-send venue data or category-based message when chat opens
  useEffect(() => {
    if (!hasSentInitial.current && messages.length === 0) {
      hasSentInitial.current = true;
      // Avoid auto-displaying backend fallbacks as 'venues' — only show real provider results
      const nonFallbackVenues = (venues || []).filter(v => v && v.provider && v.provider !== 'fallback');
      if (nonFallbackVenues.length > 0) {
        setMessages([{ role: 'assistant', venues: nonFallbackVenues.slice(0, 10) }]);
      } else if (category) {
        // Do not auto-run a backend search when the chat opens with a category selected.
        // Instead, prompt the user and offer an explicit action so the user confirms.
        const venueText = `I've explored ${neighborhood ? neighborhood + ', ' : ''}${city} and can look for ${category} options — if that's what you're into, click "Let's Go" to fetch details.`;
        setMessages([{ role: 'assistant', text: venueText }]);
      } else {
        const venueText = `I've explored ${neighborhood ? neighborhood + ', ' : ''}${city} and I'm ready to help you discover the best spots! What are you interested in - food, attractions, transport, or something else?`;
        setMessages([{ role: 'assistant', text: venueText }]);
      }
    }
  }, [venues, category, messages.length]); // Include category in dependencies

  const fetchVenuesForCategory = async () => {
    console.debug('fetchVenuesForCategory', { city, neighborhood, category });
    try {
      const payload = {
        query: city,
        category: category,
        neighborhood: neighborhood,
      };
      const resp = await fetch('http://localhost:5010/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      const fetchedVenues = (data.venues || []).filter(v => v.provider !== 'wikivoyage');
      if (fetchedVenues.length > 0) {
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

  async function sendMessage(text, query = null) {
    if (!text || !text.trim()) return;
    const msg = { role: 'user', text };
    setMessages(m => [...m, msg]);
    setInput('');
    setLoading(true);

    try {
      // Use the Groq-backed chat API on the same origin (Next.js or proxied)
      const payload = {
        // include the message we just sent so the handler has the latest user input
        messages: [...messages, msg].map(m => ({ role: m.role, text: m.text })),
        city: city,
        neighborhood: neighborhood,
        category: category,
        venues: venues,
        session_id: sessionId
      };

      // Always use the backend's decision logic for endpoint selection
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();

      // Check if request limit was reached
      if (response.status === 429 || data.limitReached) {
        setRequestLimitReached(true);
        setMessages(m => [...m, { 
          role: 'assistant', 
          text: data.message || "You've reached the limit of 1 AI request per session. To continue chatting, please close and reopen Marco to start a new session." 
        }]);
        return;
      }

      if (data && data.answer) {
        setMessages(m => [...m, { role: 'assistant', text: data.answer }]);
        if (data.session_id) {
          setSessionId(data.session_id);
        }
        // Update remaining requests counter
        if (data.requestsRemaining !== undefined) {
          setRequestsRemaining(data.requestsRemaining);
          if (data.requestsRemaining === 0) {
            setRequestLimitReached(true);
          }
        }
      } else {
        setMessages(m => [...m, { role: 'assistant', text: "I apologize, but I'm having trouble connecting. Please try again in a moment." }]);
        console.error('Groq API failed', data?.error);
      }
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', text: "I apologize, but I'm having trouble connecting. Please try again in a moment." }]);
      console.error('Chat API failed', e);
    } finally {
      setLoading(false);
    }
  }

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Helpers for rendering assistant fallback text
  const isGoogleMapsFallback = (text) => /no venues found|see more on google maps|explore more options on google maps|no detailed venues found/i.test(text || '');
  const firstSentences = (text, n = 2) => (text || '').split(/(?<=[.?!])\s+/).slice(0, n).join(' ');

  // Submit handler for the chat input
  const handleSubmit = () => {
    console.debug('handleSubmit', { category, input, loading });
    if (!input.trim() || loading) return;
    // If there's a category and no typed input, we want to fetch category venues instead
    if (category && !input.trim()) {
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

  const startNewSession = () => {
    localStorage.removeItem('marco_session_id');
    setSessionId(null);
    setRequestLimitReached(false);
    setRequestsRemaining(1);
    setMessages([]);
    hasSentInitial.current = false;
  };

  return (
    <div className="marco-modal-overlay">
      <div className="marco-modal">
        <div className="marco-header">
          <span>Marco — Travel Assistant for {neighborhood ? `${neighborhood}, ` : ''}{city}</span>
          {requestLimitReached && (
            <button 
              className="marco-new-session" 
              onClick={startNewSession}
              style={{ marginRight: 'auto', marginLeft: 12, padding: '4px 12px', fontSize: '0.85em', background: '#4CAF50', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}
            >
              ↻ New Session
            </button>
          )}
          <button className="marco-close" onClick={onClose}>×</button>
        </div>

        <div className="marco-messages" role="region" aria-live="polite">
          {messages.map((msg, i) => (
            <div key={i} className={`marco-msg ${msg.role}`}>
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
                            emoji: (venue.description || '').toLowerCase().includes('tea') ? '🫖' : (venue.description || '').toLowerCase().includes('coffee') ? '☕' : '📍',
                            sustainability: venue.tags?.includes('eco') ? '♻️' : '',
                            pricing: venue.price_level ? '💰'.repeat(venue.price_level) : '',
                            mapsUrl: venue.latitude && venue.longitude ? `https://www.google.com/maps/search/?api=1&query=${venue.latitude},${venue.longitude}` : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((venue.name || venue.title || '') + ' ' + (venue.city || ''))}`
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
                          const numberedRe = /^\d+\.\s+(.*)$/;
                          for (const line of lines) {
                            let m = line.match(bulletRe) || line.match(numberedRe);
                            if (m) {
                              items.push(m[1].replace(/^\*\*|\*\*$/g, '').trim());
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
                              // Heuristic emoji selection
                              const lower = name.toLowerCase();
                              let emoji = '📍';
                              if (/(coffee|cafe|espresso|latte|tea)/i.test(lower)) emoji = '☕';
                              else if (/(museum|gallery|historic|cathedral|monument)/i.test(lower)) emoji = '🏛️';
                              else if (/(park|garden|outdoor)/i.test(lower)) emoji = '🌳';
                              else if (/(bar|pub|cocktail|wine|beer)/i.test(lower)) emoji = '🍸';
                              // Generate a Google Maps search URL using name and city
                              const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name + (city ? ' ' + city : ''))}`;
                              return (
                                <VenueCard
                                  key={idx}
                                  venue={{
                                    name,
                                    description,
                                    emoji,
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
              <div className="loading-dots">...</div>
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
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={requestLimitReached ? "Session limit reached - click New Session button to continue" : "Ask about restaurants, attractions, travel tips..."}
            disabled={loading || requestLimitReached}
          />
          <button
            onClick={() => {
              if (category && !input.trim()) {
                fetchVenuesForCategory();
              } else {
                handleSubmit();
              }
            }}
            disabled={loading || (!input.trim() && !category) || requestLimitReached}
          >
            {loading ? '...' : requestLimitReached ? "Limit Reached" : "Let's Go"}
          </button>
          {requestLimitReached && (
            <div style={{ marginTop: 8, color: '#e74c3c', fontSize: '0.9em', textAlign: 'center' }}>
              💡 You've used your 1 AI request for this session. Click the "New Session" button above to start fresh!
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
