/** @type {import('tailwindcss').Config} */
//
// Mirrors the inline `tailwind.config = {...}` block that previously lived in
// index.html (Tailwind CDN era). Source of truth for the Claude-inspired warm
// palette + custom radii/shadows used across web/v2/.
//
// Build:  `npm run build:css`   →  ./tailwind.css
// Watch:  `npm run watch:css`   →  rebuild on edit
//
// brand-800 (#9F4D2D) is the AA-compliant body-text shade — keep it; lighter
// 500/600/700 fail WCAG 4.5:1 against cream-100.

module.exports = {
  content: ['./index.html', './app.js'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'Vazirmatn', 'system-ui', 'sans-serif'],
        fa:   ['Vazirmatn', 'Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        cream: { 50: '#FCFBF7', 100: '#FAF9F5', 200: '#F4F2EC', 300: '#EBE9E2' },
        ink:   { 900: '#1F1E1B', 700: '#3F3E3A', 500: '#73716D', 400: '#9A9893' },
        brand: { 500: '#D97757', 600: '#C8704D', 700: '#B5613E', 800: '#9F4D2D' },
      },
      borderRadius: { lg: '12px', xl: '16px', '2xl': '20px' },
      boxShadow: {
        soft: '0 1px 2px rgba(31,30,27,0.04), 0 4px 12px rgba(31,30,27,0.04)',
        card: '0 1px 3px rgba(31,30,27,0.06), 0 8px 24px rgba(31,30,27,0.06)',
        ring: '0 0 0 4px rgba(217,119,87,0.18)',
      },
    },
  },
  plugins: [],
};
