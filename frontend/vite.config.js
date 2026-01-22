import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5174,
    strictPort: true, // Don't switch to another port if 5174 is in use
    proxy: {
      '/api': 'http://localhost:5010',
      '/search': 'http://localhost:5010',
      '/neighborhoods': 'http://localhost:5010',
      '/geocode': 'http://localhost:5010'
    }
  }
});
