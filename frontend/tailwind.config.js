/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Warm paper palette
        paper: '#F4EFE6',      // page background
        surface: '#FBF8F2',    // cards, panels, inputs
        sunken: '#EDE6D9',     // hover rows, code, subtle fills
        line: '#DDD3C2',       // borders
        'line-strong': '#C9BDA8',
        ink: {
          DEFAULT: '#2B2620',  // body text
          muted: '#6B6255',    // secondary text
          faint: '#9A8F7E'     // hints, placeholders
        },
        accent: {
          DEFAULT: '#A3542F',  // terracotta
          hover: '#8C4526',
          soft: '#F1E1D3'
        },
        danger: {
          DEFAULT: '#A33A2F',
          soft: '#F5DFDA'
        },
        success: '#4F6B3A'
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        serif: ['"Source Serif 4"', 'Georgia', 'serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace']
      },
      boxShadow: {
        card: '0 1px 2px rgba(43, 38, 32, 0.06)',
        raised: '0 8px 24px rgba(43, 38, 32, 0.12)'
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' }
        }
      },
      animation: {
        'fade-in': 'fade-in 150ms ease-out',
        'slide-up': 'slide-up 180ms ease-out'
      }
    },
  },
  plugins: [],
}
