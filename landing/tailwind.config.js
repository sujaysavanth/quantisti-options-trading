/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        ink: '#1d1d1f',
        paper: '#f5f5f7',
        graphite: '#161617',
        muted: '#86868b',
        link: 'var(--link)',
        gain: 'var(--gain)',
        loss: 'var(--loss)',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'var(--font-inter)', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        eyebrow: ['1.3125rem', { lineHeight: '1.2', letterSpacing: '0.01em', fontWeight: '600' }],
        display: ['clamp(3rem, 8vw, 6rem)', { lineHeight: '1.04', letterSpacing: '-0.025em', fontWeight: '600' }],
        headline: ['clamp(2.25rem, 5.5vw, 4rem)', { lineHeight: '1.06', letterSpacing: '-0.02em', fontWeight: '600' }],
        lede: ['clamp(1.1875rem, 2vw, 1.5rem)', { lineHeight: '1.4', letterSpacing: '0.004em', fontWeight: '500' }],
      },
      borderRadius: {
        tile: '28px',
      },
    },
  },
  plugins: [],
}
