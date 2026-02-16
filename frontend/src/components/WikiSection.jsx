import { useEffect, useState } from 'react';

export default function WikiSection({ city, section = "Tourism" }) {
  const [wikiContent, setWikiContent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!city) return;

    const fetchWikiSection = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/wiki/section?page=${encodeURIComponent(city)}&section=${encodeURIComponent(section)}`);
        const data = await response.json();

        if (data.found && data.html) {
          setWikiContent(data.html);
        } else {
          setWikiContent(null);
        }
      } catch (err) {
        console.error('Failed to fetch wiki section:', err);
        setError('Failed to load Wikipedia section');
      } finally {
        setLoading(false);
      }
    };

    fetchWikiSection();
  }, [city, section]);

  if (loading) {
    return (
      <section className="wiki-section">
        <h2>Wikipedia: {section}</h2>
        <div className="wiki-loading">Loading Wikipedia content...</div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="wiki-section">
        <h2>Wikipedia: {section}</h2>
        <div className="wiki-error">{error}</div>
      </section>
    );
  }

  if (!wikiContent) {
    return null; // Don't show section if no content
  }

  const shouldCollapse = wikiContent.length > 2000 && !expanded;

  return (
    <section className="wiki-section">
      <h2>Wikipedia: {section}</h2>
      <div
        className={`wiki-html ${shouldCollapse ? 'collapsed' : 'expanded'}`}
        dangerouslySetInnerHTML={{ __html: wikiContent }}
      />
      {shouldCollapse && (
        <button
          className="read-more-btn"
          onClick={() => setExpanded(true)}
        >
          Read More
        </button>
      )}
    </section>
  );
}