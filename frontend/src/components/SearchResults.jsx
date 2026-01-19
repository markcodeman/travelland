import React, { useState } from 'react';
import QuickGuide from './QuickGuide';

export default function SearchResults({ results }) {
  // no raw JSON exposed to users by default
  if (!results) return null;
  if (results.error) return <div className="results-error">Error: {results.error}</div>;

  const quick = results.quick_guide || results.quickGuide || results.summary || null;

  return (
    <div className="search-results">
      {quick && <QuickGuide guide={quick} source={results.source} source_url={results.source_url} />}

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
