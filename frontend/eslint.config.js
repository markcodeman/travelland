import js from '@eslint/js';
import react from 'eslint-plugin-react';

export default [
  js.configs.recommended,
  {
    plugins: {
      react: react.configs.recommended,
    },
  },
  {
    rules: {
      'no-console': 'warn',
      'prefer-const': 'error',
    },
  },
  {
    overrides: [
      {
        files: ['**/*.{js,jsx,ts,tsx}'],
        rules: {
          'no-console': 'warn',
          'prefer-const': 'error',
        },
      },
    ],
  },
];
