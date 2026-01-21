import React from 'react';

const categoryMeta = {
  'Food': { color: '#f39c12', icon: '🍽️' },
  'Nightlife': { color: '#8e44ad', icon: '🌃' },
  'Culture': { color: '#3498db', icon: '🏛️' },
  'Outdoors': { color: '#27ae60', icon: '🌲' },
  'Shopping': { color: '#e67e22', icon: '🛍️' },
  'History': { color: '#95a5a6', icon: '📜' },
};

export default function CategoryChips({ categories, selectedCategory, setSelectedCategory }) {
  return (
    <div className="category-chips">
      {categories.map(cat => {
        const meta = categoryMeta[cat] || { color: '#3498db', icon: '' };
        return (
          <button
            key={cat}
            className={`category-chip${selectedCategory === cat ? ' selected' : ''}`}
            onClick={() => setSelectedCategory(selectedCategory === cat ? '' : cat)}
            style={{ background: selectedCategory === cat ? meta.color : undefined, border: `1px solid ${meta.color}` }}
            title={cat}
          >
            <span style={{ marginRight: 8 }}>{meta.icon}</span>
            {cat}
          </button>
        );
      })}
    </div>
  );
}
