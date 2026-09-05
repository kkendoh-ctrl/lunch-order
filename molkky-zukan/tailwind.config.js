/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // 色は2系統。墨(ink)＝地の色、琥珀(amber)＝差し色。
      colors: {
        ink: {
          50: '#f6f6f4',
          100: '#e9e9e4',
          200: '#d3d3ca',
          300: '#adaea1',
          400: '#83857a',
          500: '#63655c',
          600: '#4c4e47',
          700: '#3b3d38',
          800: '#262824',
          900: '#181a17',
          950: '#0f100e',
        },
        amber: {
          50: '#fbf7ed',
          100: '#f4e9cd',
          200: '#e8d29c',
          300: '#dbb765',
          400: '#cf9f3d',
          500: '#b9862c',
          600: '#996a24',
          700: '#7a5220',
          800: '#5f4020',
          900: '#4f351d',
        },
      },
      fontFamily: {
        gothic: [
          'system-ui',
          '-apple-system',
          '"Hiragino Kaku Gothic ProN"',
          '"Noto Sans JP"',
          'Meiryo',
          'sans-serif',
        ],
        mincho: [
          '"Hiragino Mincho ProN"',
          '"Yu Mincho"',
          '"Noto Serif JP"',
          '"MS PMincho"',
          'serif',
        ],
      },
      boxShadow: {
        card: '0 1px 2px rgba(15,16,14,.06), 0 8px 24px -12px rgba(15,16,14,.35)',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
      animation: {
        'fade-up': 'fade-up .28s ease-out both',
      },
    },
  },
  plugins: [],
}
