# Contributing Guidelines

Quick note for contributors working on provider modules (e.g., overpass_provider):

- BEFORE creating a new file/module, always search the repository for existing modules with the same name. Duplicating module names across package roots leads to confusion and import conflicts.
- Prefer adding functionality to the canonical implementation under `city_guides/providers/`.
- If you need to preserve compatibility for older imports, add a small shim under `city_guides/` that re-exports the canonical implementation (see `city_guides/overpass_provider.py`).
- Add or update unit tests when you change provider discovery behavior. If you create a new top-level shim, add a test in `tests/` to ensure the shim exists and correctly re-exports the implementation.

Example workflow:
1. Search: `git grep overpass_provider` or `rg overpass_provider`.
2. If provider exists under `city_guides/providers/`, add or modify code there.
3. If you must add a top-level module for compatibility, create a shim file that `from city_guides.providers.overpass_provider import *` and add a test to `tests/`.

Thanks for keeping the repo tidy! 🎯
