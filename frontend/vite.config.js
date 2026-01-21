import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/search': 'http://localhost:5010',
      '/neighborhoods': 'http://localhost:5010',
      '/geocode': 'http://localhost:5010'
    }
  }
});
