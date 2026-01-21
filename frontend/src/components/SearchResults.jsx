import React, { useState } from 'react';
import QuickGuide from './QuickGuide';

export default function SearchResults({ results }) {
  // no raw JSON exposed to users by default
  if (!results) return null;
  if (typeof results !== 'object') return <div className="results-error">Invalid results data</div>;
  if (results.error) return <div className="results-error">Error: {results.error}</div>;

  const quick = results.quick_guide || results.quickGuide || results.summary || null;
  const images = results.mapillary_images || results.images || null;
  const venues = results.venues || [];
  const wikivoyage = results.wikivoyage || [];
  const costs = results.costs || [];
  const transport = results.transport || [];

  return (
    <div className="search-results">
      {quick && <QuickGuide guide={quick} images={images} source={results.source} source_url={results.source_url} />}

      {venues.length > 0 && (
        <section>
          <h2>Venues</h2>
          <ul>
            {venues.map((v, i) => (
              <li key={i}>
                <strong>
                  {v.lat && v.lon ? (
                    <a href={`https://maps.google.com/maps?q=${v.lat},${v.lon}`} target="_blank" rel="noopener noreferrer">
                      {v.name}
                    </a>
                  ) : (
                    v.name
                  )}
                </strong> - {v.description || v.address || v.type}
                {v.url && <a href={v.url} target="_blank" rel="noopener noreferrer"> (link)</a>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {wikivoyage.length > 0 && (
        <section>
          <h2>Travel Info</h2>
          {wikivoyage.map((w, i) => (
            <div key={i} className="wikivoyage-section">
              <h3>{w.title || w.section}</h3>
              <p>{w.content || w.text}</p>
              {w.wikivoyage_url && <a href={w.wikivoyage_url} target="_blank" rel="noopener noreferrer">Read more on Wikivoyage</a>}
            </div>
          ))}
        </section>
      )}

      {costs.length > 0 && (
        <section>
          <h2>Cost Estimates</h2>
          <ul>
            {costs.map((c, i) => (
              <li key={i}>
                <strong>{c.category}</strong>: {c.description} ({c.currency} {c.amount})
              </li>
            ))}
          </ul>
        </section>
      )}

      {transport.length > 0 && (
        <section>
          <h2>Transport</h2>
          <ul>
            {transport.map((t, i) => (
              <li key={i}>
                <a href={t.url} target="_blank" rel="noopener noreferrer">{t.name}</a>
              </li>
            ))}
          </ul>
        </section>
      )}

      {results.weather && (
        <section>
          <h2>Weather</h2>
          <pre>{JSON.stringify(results.weather, null, 2)}</pre>
        </section>
      )}

      {results.debug && (
        <section>
          <h2>Debug Info</h2>
          <pre>{JSON.stringify(results.debug, null, 2)}</pre>
        </section>
      )}

      {/* Raw JSON intentionally hidden from UI to avoid exposing internals */}
    </div>
  );
}
