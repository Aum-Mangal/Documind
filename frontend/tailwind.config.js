/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#0B0F19',
        surface: '#111827',
        surfaceLight: '#1F2937',
        border: '#374151',
        primary: '#3B82F6',
        primaryHover: '#2563EB',
        accent: '#8B5CF6',
        textMuted: '#9CA3AF'
      }
    },
  },
  plugins: [],
}
