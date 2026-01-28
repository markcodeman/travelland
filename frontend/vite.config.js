import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  css: {
    postcss: './postcss.config.js',
  },
  server: {
    host: '0.0.0.0',
    port: 5174,
    strictPort: true, // Don't switch to another port if 5174 is in use
    proxy: {
      '/api/chat': 'http://localhost:3000',
      '/api': 'http://localhost:5010',
      '/search': 'http://localhost:5010',
      '/synthesize': 'http://localhost:5010',
      '/neighborhoods': 'http://localhost:5010',
      '/geocode': 'http://localhost:5010',
      // Backend endpoints used without /api prefix in the frontend
      '/weather': 'http://localhost:5010',
      '/generate_quick_guide': 'http://localhost:5010',
      '/semantic-search': 'http://localhost:5010'
    }
  }
});
