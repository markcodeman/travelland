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
          <h2>Venues <span className="section-sub">({results.debug_info && results.debug_info.venues_source === 'osm' ? 'Local data' : 'Results'})</span></h2>
          <div className="venues-grid">
            {venues.map((v, i) => (
              <article key={i} className="venue-card">
                <div className="venue-card-head">
                  <div className="venue-title">
                    {v.latitude && v.longitude ? (
                      <a href={`https://www.google.com/maps/search/?api=1&query=${v.latitude},${v.longitude}`} target="_blank" rel="noopener noreferrer">{v.name}</a>
                    ) : v.lat && v.lon ? (
                      <a href={`https://www.google.com/maps/search/?api=1&query=${v.lat},${v.lon}`} target="_blank" rel="noopener noreferrer">{v.name}</a>
                    ) : (
                      <span>{v.name}</span>
                    )}
                    {v.provider === 'wikivoyage' && <span className="badge-wikivoyage">WIKIVOYAGE</span>}
                  </div>
                  <div className="venue-price">{v.price_range || ''}</div>
                </div>
                <div className="venue-body">
                  <p className="venue-text">{v.description && v.description.length > 240 ? v.description.slice(0,240) + '…' : (v.description || v.address || '')}</p>
                </div>
                <div className="venue-actions">
                  {v.website && <a className="btn-link" href={v.website} target="_blank" rel="noopener noreferrer">Website</a>}
                  {/* Directions always link to Google Maps */}
                  <a className="btn-link" href={
                    (v.latitude && v.longitude) || (v.lat && v.lon) ?
                      `https://www.google.com/maps/search/?api=1&query=${v.latitude||v.lat},${v.longitude||v.lon}` :
                      `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(v.name + ' ' + v.city)}`
                  } target="_blank" rel="noopener noreferrer">Directions</a>
                </div>
              </article>
            ))}
          </div>
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
