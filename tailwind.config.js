/** Tailwind build for the prototype UI.
 *  Content must cover every file that emits class names, including the JS
 *  templates - that is where most of the markup lives. */
module.exports = {
  content: ['./index.html', './static/js/**/*.js'],
  darkMode: 'class',
  theme: {
    extend: {
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        fadeIn: 'fadeIn .35s cubic-bezier(.16,1,.3,1) both',
      },
    },
  },
  plugins: [],
}
