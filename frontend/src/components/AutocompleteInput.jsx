import React, { useState, useRef, useEffect } from 'react';

export default function AutocompleteInput({ label, options, value, setValue, placeholder }) {
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef(null);

  useEffect(() => {
    setActiveIndex(-1);
  }, [suggestions]);

  function handleChange(e) {
    const input = e.target.value;
    setValue(input);
    if (input.length > 0) {
      const filtered = options.filter(opt => opt.toLowerCase().includes(input.toLowerCase()));
      // remove duplicates while preserving order
      const unique = Array.from(new Set(filtered));
      setSuggestions(unique);
      setShowSuggestions(true);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }

  function handleSuggestionClick(suggestion) {
    setValue(suggestion);
    setSuggestions([]);
    setShowSuggestions(false);
    setActiveIndex(-1);
  }

  function handleKeyDown(e) {
    if (!showSuggestions || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      setActiveIndex(idx => (idx + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      setActiveIndex(idx => (idx <= 0 ? suggestions.length - 1 : idx - 1));
    } else if (e.key === 'Enter') {
      if (activeIndex >= 0 && activeIndex < suggestions.length) {
        handleSuggestionClick(suggestions[activeIndex]);
        e.preventDefault();
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  }

  function handleBlur() {
    setTimeout(() => setShowSuggestions(false), 100);
  }

  return (
    <div className="autocomplete-input">
      <label>{label}
        <input
          type="text"
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          onFocus={handleChange}
          placeholder={placeholder}
          autoComplete="off"
          ref={inputRef}
        />
      </label>
      {showSuggestions && suggestions.length > 0 && (
        <ul className="suggestions-list">
          {suggestions.map((s, i) => (
            <li
              key={`${s}-${i}`}
              className={i === activeIndex ? 'active' : ''}
              onMouseDown={() => handleSuggestionClick(s)}
            >
              {s}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
