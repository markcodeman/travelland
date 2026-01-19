import React from 'react';

export default function QuickGuide({ guide, source, source_url }) {
  if (!guide) return null;
  return (
    <div className="quick-guide">
      <h2>Quick guide</h2>
      <p>{guide}</p>
      {source && (
        <div className="quick-source">Source: {source}{source_url ? (<a href={source_url} target="_blank" rel="noreferrer"> ↗</a>) : null}</div>
      )}
    </div>
  );
}
