import React from 'react';

export default function Header() {
  return (
    <header className="hero">
      <div className="hero-inner">
        <div className="mobile-banner">
          {/* Horizontal banner logo */}
          <img 
            src="/marcobanner.png" 
            alt="Marco's Microguide banner" 
            className="mobile-logo-horizontal"
          />
          
          {/* Brand text and tagline for desktop only */}
          <div className="desktop-only">
            <div className="brand-section">
              <div className="mobile-brand">
                <div className="mobile-title">Marco's</div>
                <div className="mobile-subtitle">Micro City Guides</div>
              </div>
            </div>
            <div className="hero-text">
              <h2>AI-Powered City Exploration</h2>
              <p>Chat with Marco, your AI travel guide, to discover neighborhoods and get personalized recommendations.</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
