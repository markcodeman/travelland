import React, { useState, useEffect, useRef } from 'react';

export default function MarcoChat({ city, neighborhood, venues, category, wikivoyage, onClose }) {
  const [messages, setMessages] = useState([]); // {role: 'user'|'assistant', text}
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState(localStorage.getItem('marco_session_id') || null);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef(null);
  const hasSentInitial = useRef(false);

  useEffect(() => {
    if (sessionId) localStorage.setItem('marco_session_id', sessionId);
  }, [sessionId]);

  // Auto-send venue data or category-based message when chat opens
  useEffect(() => {
    if (!hasSentInitial.current && messages.length === 0) {
      hasSentInitial.current = true;
      let venueText;
      if (venues && venues.length > 0) {
        venueText = `Here are some great places I found in ${neighborhood ? neighborhood + ', ' : ''}${city}:\n\n${venues.map((v, i) => `${i + 1}. ${v.name || v.title} - ${v.description || v.address || 'No description'}`).join('\n')}\n\nWhat would you like to know about these places?`;
      } else if (category) {
        const cLower = (category || '').toLowerCase();
        let action = 'prepare';
        if (cLower.includes('coffee')) action = 'brew';
        else if (cLower.includes('tea')) action = 'steep';
        else if (cLower.includes('pizza')) action = 'bake';
        else if (cLower.includes('sushi')) action = 'roll';
        else if (cLower.includes('beer')) action = 'pour';
        else if (cLower.includes('wine')) action = 'uncork';
        else if (cLower.includes('dessert')) action = 'bake';
        else if (cLower.includes('taco')) action = 'grill';

        venueText = `I've explored ${neighborhood ? neighborhood + ', ' : ''}${city} and found some great ${category} options! Standby while I ${action} them up.`;
      } else {
        venueText = `I've explored ${neighborhood ? neighborhood + ', ' : ''}${city} and I'm ready to help you discover the best spots! What are you interested in - food, attractions, transport, or something else?`;
      }
      if (category) {
        sendMessage(venueText, `List some great ${category} options in ${neighborhood ? neighborhood + ', ' : ''}${city}. Format the response as bullet points: - Venue Name: Brief description`);
      } else {
        sendMessage(venueText);
      }
    }
  }, [venues, category, messages.length]); // Include category in dependencies

  async function sendMessage(text, query = null) {
    if (!text || !text.trim()) return;
    const msg = { role: 'user', text };
    setMessages(m => [...m, msg]);
    setInput('');
    setLoading(true);
    try {
      const payload = {
        q: query || text,
        city: city || undefined,
        neighborhoods: neighborhood ? [{ name: neighborhood }] : undefined,
        venues: venues || undefined,
        category: category || undefined,
        wikivoyage: wikivoyage || undefined,
        mode: 'explorer',
        session_id: sessionId,
        history: buildConversationHistory(messages),
      };
      const resp = await fetch('http://localhost:5010/semantic-search', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      const j = await resp.json();
      if (j && j.answer) {
        const assistantText = typeof j.answer === 'string' ? j.answer : (j.answer.answer || JSON.stringify(j.answer));
        setMessages(m => [...m, { role: 'assistant', text: assistantText }]);
      }
      if (j && j.session_id) {
        setSessionId(j.session_id);
      }
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', text: "Ahoy! Marco is having a snooze. Try again in a moment." }]);
      console.error('Marco chat failed', e);
    } finally {
      setLoading(false);
      // scroll
      if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight;
    }
  }

  const buildConversationHistory = (messages) => {
    return messages
      .map(msg => `${msg.role === 'user' ? 'User' : 'Marco'}: ${msg.text || msg.content || ''}`)
      .join('\n');
  };

  return (
    <div className="marco-modal-overlay">
      <div className="marco-modal">
        <div className="marco-header">
          <span>Marco — Ask me anything about {neighborhood ? neighborhood + ', ' : ''}{city || ''}</span>
          <button className="marco-close" onClick={onClose}>×</button>
        </div>
        <div className="marco-messages" ref={boxRef}>
          {messages.map((m, i) => (
            <div key={i} className={`marco-msg ${m.role}`}>{m.text}</div>
          ))}
        </div>
        <div className="marco-input">
          <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') sendMessage(input); }} placeholder="Ask Marco a question" />
          <button disabled={loading} onClick={() => sendMessage(input)}>{loading ? '...' : 'Send'}</button>
        </div>
      </div>
    </div>
  );
}
