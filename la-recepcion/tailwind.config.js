/** @type {import('tailwindcss').Config} */
// La Recepción no compila Tailwind aún (S1a stub usa CDN). Este config queda
// listo para S5 cuando lleguen las vistas reales. `darkMode: 'class'` armado
// desde ahora para coherencia con La Gerencia y El Taller.
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
