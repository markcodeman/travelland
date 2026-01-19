import React, { useState, useRef, useEffect } from 'react';

// options: array of strings
export default function NeighborhoodSelect({ options = [], value = '', onChange }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef(null);

  useEffect(() => {
    function onDoc(e) {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const filtered = options.filter(o => o.toLowerCase().includes(query.toLowerCase()));

  // group by first letter
  const groups = filtered.reduce((acc, item) => {
    const key = item[0].toUpperCase();
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});

  const groupKeys = Object.keys(groups).sort();

  const total = options.length;

  function openToggle() {
    setOpen(o => !o);
    setQuery('');
    setActiveIndex(-1);
  }

  function handleSelect(val) {
    onChange && onChange(val);
    setOpen(false);
  }

  function onKeyDown(e) {
    if (!open) return;
    const items = Array.from(containerRef.current.querySelectorAll('.ns-item'));
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const next = Math.min(activeIndex + 1, items.length - 1);
      setActiveIndex(next);
      items[next] && items[next].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = Math.max(activeIndex - 1, 0);
      setActiveIndex(prev);
      items[prev] && items[prev].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIndex >= 0 && items[activeIndex]) {
        const v = items[activeIndex].getAttribute('data-value');
        handleSelect(v);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  }

  return (
    <div className="neighborhood-select" ref={containerRef}>
      <div className="ns-control">
        <button type="button" className="ns-toggle" onClick={openToggle} aria-expanded={open}>
          {value || `All Areas (${total} neighborhoods)`}
        </button>
        <div className="ns-search-wrap">
          <input
            className="ns-search"
            placeholder="Search areas..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
            aria-label="Search neighborhoods"
          />
        </div>
      </div>

      {open && (
        <div className="ns-dropdown" role="listbox">
          <div className="ns-top-option ns-item" data-value="" onClick={() => handleSelect('')} tabIndex={0}>
            All Areas ({total} neighborhoods)
          </div>
          <div className="ns-list">
            {groupKeys.length === 0 && <div className="ns-empty">No matching areas</div>}
            {groupKeys.map((k) => (
              <div key={k} className="ns-group">
                <div className="ns-group-header">{k}</div>
                {groups[k].map((it, i) => (
                  <div
                    key={it}
                    className={`ns-item ${value === it ? 'selected' : ''}`}
                    data-value={it}
                    onClick={() => handleSelect(it)}
                    tabIndex={0}
                  >
                    {it}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
