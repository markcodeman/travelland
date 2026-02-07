# 🔒 BRANCH SCOPE LOCK: enhance-marco-chat

**Created:** Feb 6, 2026  
**Purpose:** Enhance Marco AI chat UI/UX only

## ✅ ALLOWED (Touch These)
- `frontend/src/components/MarcoChat.jsx`
- `frontend/src/components/MarcoChat.css`
- Any files with "marco" in the name (case insensitive)

## 🚫 FORBIDDEN (Don't Touch)
- `city_guides/src/app.py` (API endpoints)
- `city_guides/data/**/*.json` (seed data files)
- `frontend/src/components/NeighborhoodPicker.jsx`
- `frontend/src/components/CitySuggestions.jsx`
- `frontend/src/components/SearchResults.jsx`
- `frontend/src/components/HeroImage.jsx`
- Any backend logic or data handling

## 🎯 Focus Areas for Marco
- Chat interface design
- Message bubbles and typography
- Input styling
- Response formatting
- Animation/transitions
- Mobile responsiveness for chat
- Quick reply suggestions UI

## 🛡️ Protection Active
Pre-commit hook installed at `.git/hooks/pre-commit`  
**Blocks commits** of non-Marco files on this branch.

**To bypass (not recommended):** `git commit --no-verify`

## Commit Message Format
```
[Marco] <what you changed>

Examples:
[Marco] Improve message bubble styling
[Marco] Add typing indicator animation
[Marco] Fix mobile chat layout
```

## When Done
1. Test Marco chat thoroughly
2. `git checkout main`
3. `git merge enhance-marco-chat`
4. `git push origin main`

---
**Remember:** If the file doesn't have "marco" in the name, DON'T EDIT IT ON THIS BRANCH.
