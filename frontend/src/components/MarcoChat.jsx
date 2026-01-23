import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import VenueCard from './VenueCard';
import './MarcoChat.css';

export default function MarcoChat({ city, neighborhood, venues, category, initialInput, onClose }) {
  const [messages, setMessages] = useState([]); // {role: 'user'|'assistant', text}
  const [input, setInput] = useState(initialInput || ''); // allow initial input
  const [sessionId, setSessionId] = useState(localStorage.getItem('marco_session_id') || null);
  const [loading, setLoading] = useState(false);
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
      if (venues && venues.length > 0) {
        setMessages([{ role: 'assistant', venues }]);
      } else if (category) {
        // Do not auto-run a backend search when the chat opens with a category selected.
        // Instead, prompt the user and offer a Search button so the user explicitly confirms.
        const venueText = `I've explored ${neighborhood ? neighborhood + ', ' : ''}${city} and can look for ${category} options — click Search to fetch details.`;
        setMessages([{ role: 'assistant', text: venueText }]);
      } else {
        const venueText = `I've explored ${neighborhood ? neighborhood + ', ' : ''}${city} and I'm ready to help you discover the best spots! What are you interested in - food, attractions, transport, or something else?`;
        setMessages([{ role: 'assistant', text: venueText }]);
      }
    }
  }, [venues, category, messages.length]); // Include category in dependencies

  const fetchVenuesForCategory = async () => {
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

      const response = await fetch('/api/chat', {
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
      setLoading(false);
    }
  }

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = () => {
    if (!input.trim() || loading) return;
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

        <div className="marco-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`marco-msg ${msg.role}`}>
              {msg.role === 'assistant' && msg.venues ? (
                <div>
                  <div style={{fontWeight:700, fontSize:'1.1em', marginBottom:8}}>☕ Here are some great places I found:</div>
                  {msg.venues && msg.venues.length > 0 ? (
                    msg.venues.map((venue, idx) => (
                      <VenueCard key={venue.id || idx} venue={{
                        ...venue,
                        emoji: (venue.description || '').toLowerCase().includes('tea') ? '🫖' : (venue.description || '').toLowerCase().includes('coffee') ? '☕' : '📍',
                        mapsUrl: venue.latitude && venue.longitude ? `https://www.google.com/maps/search/?api=1&query=${venue.latitude},${venue.longitude}` : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((venue.name || venue.title || '') + ' ' + (venue.city || ''))}`
                      }}
                      onDirections={(v) => window.open(`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(v.address || v.name + ' ' + (v.city || ''))}`,'_blank')}
                      onMap={(v) => window.open(v.mapsUrl, '_blank')}
                      onSave={null}
                      />
                    ))
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
                      show a client-side fallback VenueCard so the UI always displays a card layout. */}
                  {(() => {
                    const text = msg.text || '';
                    const looksLikeList = /\n\s*\d+\./.test(text) || /here are (a few|some) recommendations/i.test(text);
                    if (looksLikeList) {
                      return (
                        <div style={{marginTop:12}}>
                          <VenueCard key="fallback-google-maps-md" venue={{
                            id: 'google-maps-fallback-md',
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
                        </div>
                      );
                    }
                    return null;
                  })()}
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

        <div className="marco-input">
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
