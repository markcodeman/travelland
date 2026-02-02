import React, { useState, useEffect } from 'react';
import './FunFact.css';

const FunFact = ({ city }) => {
  const [funFact, setFunFact] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!city) return;

    const fetchFunFact = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const response = await fetch('/api/fun-fact', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ city })
        });

        if (response.ok) {
          const data = await response.json();
          setFunFact(data.funFact);
        } else {
          setError('Could not load fun fact');
        }
      } catch (err) {
        console.error('Failed to fetch fun fact:', err);
        setError('Failed to load fun fact');
      } finally {
        setLoading(false);
      }
    };

    fetchFunFact();
  }, [city]);

  if (!city) return null;
  if (loading) return (
    <div className="fun-fact fun-fact--loading">
      <div className="fun-fact-header">
        <span className="fun-fact-icon">💡</span>
        <span className="fun-fact-title">FUN FACT</span>
      </div>
      <div className="fun-fact-loading">
        <div className="fun-fact-shimmer"></div>
      </div>
    </div>
  );
  if (error) return null;
  if (!funFact) return null;

  return (
    <div className="fun-fact">
      <div className="fun-fact-header">
        <span className="fun-fact-icon">💡</span>
        <span className="fun-fact-title">FUN FACT about {city.toUpperCase()}</span>
      </div>
      <div className="fun-fact-content">
        {funFact}
      </div>
    </div>
  );
};

export default FunFact;
