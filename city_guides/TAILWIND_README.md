Tailwind build (minimal)
=========================

This project includes a minimal Tailwind build setup for production-optimized CSS.

Quick steps:

1. Install dependencies (requires Node.js & npm):

```bash
cd city_guides
npm install
```

2. Build CSS:

```bash
npm run build:css
```

The generated, minified stylesheet will be written to `city_guides/static/tailwind.css`.

3. For development watch mode:

```bash
npm run watch:css
```

Notes:
- The current HTML still includes the Tailwind CDN for prototyping. Replace that reference with `/static/tailwind.css` in `templates/index.html` when you are ready to serve the built CSS.
- Before deploying, enable PurgeCSS via the `content` paths in `tailwind.config.cjs` (already configured) to remove unused CSS.
