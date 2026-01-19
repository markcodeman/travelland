import React from 'react';

export default function ResultArea({ loading, result }) {
  if (loading) return <div className="result-area"><p>Loading...</p></div>;
  if (!result) return <div className="result-area"><p>No results yet.</p></div>;

  if (result.error) {
    return <div className="result-area error"><p>Error: {result.error}</p></div>;
  }

  return (
    <div className="result-area">
      {result.summary && (
        <section>
          <h2>Summary</h2>
          <p>{result.summary}</p>
        </section>
      )}
      {result.weather && (
        <section>
          <h2>Weather</h2>
          <pre>{JSON.stringify(result.weather, null, 2)}</pre>
        </section>
      )}
      {result.debug && (
        <section>
          <h2>Debug Info</h2>
          <pre>{JSON.stringify(result.debug, null, 2)}</pre>
        </section>
      )}
      {/* Fallback: show all if not parsed above */}
      {!result.summary && !result.weather && !result.debug && (
        <pre>{JSON.stringify(result, null, 2)}</pre>
      )}
    </div>
  );
}
