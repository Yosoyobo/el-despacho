/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./apps/**/forms.py",
    "./apps/**/views.py",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
