# NEIGHBORHOOD BRANCH SCOPE LOCK 🔒

## Branch: `enhance-neighborhood-picker`

**Created:** Feb 6, 2025  
**Purpose:** Focused enhancement of NeighborhoodPicker component ONLY

---

## ✅ ALLOWED Files

You can ONLY modify files matching these patterns:

- `NeighborhoodPicker.jsx` - Main component
- `NeighborhoodPicker.css` - Component styles
- Any file with `neighborhood` in the filename
- Documentation files with `neighborhood` in name

---

## 🚫 FORBIDDEN Files

DO NOT touch these, even if they seem related:

- **API endpoints** (`city_guides/src/app.py`)
- **Data files** (`city_guides/data/*.json`)
- **Other components** (`MarcoChat.jsx`, `CityPicker.jsx`, etc.)
- **Backend logic** (Python files in `city_guides/`)
- **Global styles** (`App.css`, etc.)
- **Configuration files** (`.gitignore`, `package.json`, etc.)

---

## 🎯 Scope Focus

This branch is for:
- UI/UX improvements to neighborhood selection
- Better neighborhood card display
- Improved filtering/sorting of neighborhoods
- Enhanced neighborhood descriptions
- Better mobile experience for neighborhood picker
- Loading states and error handling for neighborhoods

NOT for:
- Changing how neighborhoods are fetched from API
- Adding new data sources
- Modifying other components
- Backend changes

---

## 🔧 Override

To bypass (use sparingly):
```bash
git commit --no-verify
```

---

## Context

See `MARCO_BRANCH_SCOPE.md` for similar setup on MarcoChat branch.
