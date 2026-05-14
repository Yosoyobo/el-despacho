/** @type {import('tailwindcss').Config} */
module.exports = {
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
