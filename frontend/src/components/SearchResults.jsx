import React, { useState } from 'react';
import QuickGuide from './QuickGuide';

export default function SearchResults({ results, cityImage, cityImageMeta }) {
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
  const [showVenues, setShowVenues] = useState(false);

  const getMapsUrl = (v) => {
    if (v.place_id) return `https://www.google.com/maps/place/?q=place_id:${v.place_id}`;
    if (v.address) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(v.name + ' ' + v.address)}`;
    return `https://www.google.com/maps/search/?api=1&query=${v.lat},${v.lon}`;
  };

  return (
    <div className="search-results">
      {quick && <QuickGuide guide={quick} images={images} source={results.source} source_url={results.source_url} cityImage={cityImage} cityImageMeta={cityImageMeta} />}

      {venues.length > 0 && (
        <section>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ marginBottom: 0 }}>Venues <span className="section-sub">({results.debug_info && results.debug_info.venues_source === 'osm' ? 'Local data' : 'Results'})</span></h2>
            <button className="venues-toggle" onClick={() => setShowVenues(v => !v)}>
              {showVenues ? 'Hide' : 'Show'} venues
            </button>
          </div>
          {showVenues && (
            <div className="venues-grid">
              {venues.map((v, i) => (
                <article key={i} className="venue-card">
                  {v.images && v.images.length > 0 && (
                    <div className="venue-image">
                      <img src={v.images[0].url} alt={v.name} onError={(e) => e.target.style.display='none'} />
                    </div>
                  )}
                  <div className="venue-card-head">
                    <div className="venue-title">
                      {v.name ? (
                        <a href={getMapsUrl(v)} target="_blank" rel="noopener noreferrer">{v.name}</a>
                      ) : (
                        <span>{v.name}</span>
                      )}
                      {v.provider === 'wikivoyage' && <span className="badge-wikivoyage">WIKIVOYAGE</span>}
                    </div>
                    <div className="venue-price">{v.price_range || ''}</div>
                  </div>
                  <div className="venue-body">
                    <p className="venue-text">{v.description && v.description.length > 240 ? v.description.slice(0,240) + '…' : (v.description || '')}</p>
                    {v.address && !v.address.includes(',') && <p className="venue-address"> {v.address}</p>}
                    {v.address && v.address.includes(',') && <p className="venue-address"> Tokyo, Japan</p>}
                  </div>
                  <div className="venue-actions">
                    {v.website && <a className="btn-link" href={v.website} target="_blank" rel="noopener noreferrer">Website</a>}
                    <a className="btn-link" href={getMapsUrl(v)} target="_blank" rel="noopener noreferrer">Directions</a>
                  </div>
                </article>
              ))}
            </div>
          )}
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
