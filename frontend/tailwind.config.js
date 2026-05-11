/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        /* Apple dark surfaces */
        'surface-0': 'var(--surface-0)',
        'surface-1': 'var(--surface-1)',
        'surface-2': 'var(--surface-2)',
        'surface-3': 'var(--surface-3)',
        'surface-4': 'var(--surface-4)',
        'surface-5': 'var(--surface-5)',
        /* iOS system colors */
        'ios-blue':   'var(--blue)',
        'ios-green':  'var(--green)',
        'ios-red':    'var(--red)',
        'ios-orange': 'var(--orange)',
        'ios-yellow': 'var(--yellow)',
        'ios-indigo': 'var(--indigo)',
        'ios-teal':   'var(--teal)',
        'ios-purple': 'var(--purple)',
        /* Text */
        'text-primary':   'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-tertiary':  'var(--text-tertiary)',
        /* Legacy aliases */
        'bg-primary':   'var(--surface-1)',
        'bg-secondary': 'var(--surface-2)',
        'bg-card':      'var(--surface-3)',
        'accent-green': 'var(--green)',
        'accent-cyan':  'var(--blue)',
        'accent-red':   'var(--red)',
        'accent-yellow':'var(--yellow)',
        'accent':       'var(--blue)',
        'text-dim':     'var(--text-secondary)',
        'border-color': 'var(--border)',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'SF Pro Display', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SF Mono"', '"Fira Code"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        'sm':  'var(--radius-sm)',
        'md':  'var(--radius-md)',
        'lg':  'var(--radius-lg)',
        'xl':  'var(--radius-xl)',
        '2xl': '24px',
      },
      boxShadow: {
        'sm':       'var(--shadow-sm)',
        'md':       'var(--shadow-md)',
        'lg':       'var(--shadow-lg)',
        'xl':       'var(--shadow-xl)',
        'glass':    '0 8px 32px rgba(0,0,0,0.4)',
        'card':     '0 2px 8px rgba(0,0,0,0.3)',
        'elevated': '0 12px 24px rgba(0,0,0,0.5)',
      },
      animation: {
        'shimmer':    'shimmer 1.5s infinite',
        'spring-in':  'spring-in 0.25s cubic-bezier(0.34,1.56,0.64,1) forwards',
        'slide-up':   'slide-up 0.2s cubic-bezier(0.25,0.46,0.45,0.94) forwards',
        'fade-in':    'fade-in 0.2s ease forwards',
      },
      keyframes: {
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'spring-in': {
          '0%':   { opacity: '0', transform: 'scale(0.95) translateY(8px)' },
          '100%': { opacity: '1', transform: 'scale(1) translateY(0)' },
        },
        'slide-up': {
          '0%':   { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
