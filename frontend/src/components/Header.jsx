import React from 'react';

export default function Header() {
  return (
    <header className="hero">
      <div className="hero-inner">
        <div className="logo-wrap">
          {/* Use the new logo from the public directory */}
          <img src="/marcos.png" alt="Marco's Microguide logo" style={{ width: 180, height: 'auto', borderRadius: 12, background: '#fff', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }} />
          <div className="brand">
            <div className="brand-title">Marco's</div>
            <div className="brand-sub">Micro City Guides</div>
          </div>
        </div>
        <div className="hero-text">
          <h2>AI-Powered City Exploration</h2>
          <p>Chat with Marco, your AI travel guide, to discover neighborhoods and get personalized recommendations.</p>
        </div>
      </div>
    </header>
  );
}
