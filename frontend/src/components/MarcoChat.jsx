import React, { useState, useEffect, useRef } from 'react';

export default function MarcoChat({ city, neighborhood, venues }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]); // {role: 'user'|'assistant', text}
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState(localStorage.getItem('marco_session_id') || null);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef(null);

  useEffect(() => {
    if (sessionId) localStorage.setItem('marco_session_id', sessionId);
  }, [sessionId]);

  function toggle() {
    setOpen(o => !o);
  }

  async function sendMessage(text) {
    if (!text || !text.trim()) return;
    const msg = { role: 'user', text };
    setMessages(m => [...m, msg]);
    setInput('');
    setLoading(true);
    try {
      const payload = {
        q: text,
        city: city || undefined,
        neighborhoods: neighborhood ? [{ name: neighborhood }] : undefined,
        venues: venues || undefined,
        mode: 'explorer',
        session_id: sessionId,
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

  return (
    <div>
      <button id="marcoFab" className="marco-fab" onClick={toggle}>Marco</button>
      {open && (
        <div className="marco-panel">
          <div className="marco-header">Marco — Ask me anything about {neighborhood ? neighborhood + ', ' : ''}{city || ''}</div>
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
      )}
    </div>
  );
}
