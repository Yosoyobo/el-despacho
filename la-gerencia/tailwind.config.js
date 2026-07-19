/** @type {import('tailwindcss').Config} */
// Tokens portados de TailAdmin Pro 2.3.0 (Tailwind v4 CSS-first) a Tailwind v3
// JS config para El Despacho. Sprint S-TailAdmin-1.
//
// Cualquier cambio aquí hay que replicarlo en el-taller/tailwind.config.js y
// la-recepcion/tailwind.config.js (dos copias sincronizadas — patrón de
// partials del sprint). Si surge drift, unificar en sprint futuro.
module.exports = {
  darkMode: 'class',
  // El Site: gauges/sparklines arman clases de color desde Python
  // (text/bg/fill/stroke-{success,warning,error}-500). No purgar.
  safelist: [
    // Charts: gauges/sparklines arman clases desde Python.
    'text-success-500', 'text-warning-500', 'text-error-500',
    'bg-success-500', 'bg-warning-500', 'bg-error-500',
    'fill-success-500', 'fill-warning-500', 'fill-error-500',
    'stroke-success-500', 'stroke-warning-500', 'stroke-error-500',
    // _kpi_card_hero.html: color dinámico del icono pill.
    // Tonos: brand / success / error / warning / blue-light / orange / purple
    { pattern: /^bg-(brand|success|error|warning|blue-light|orange|purple)-(50|500)$/ },
    { pattern: /^text-(brand|success|error|warning|blue-light|orange|purple)-(400|500|600|700)$/ },
    { pattern: /^bg-(brand|success|error|warning|blue-light|orange|purple)-500\/(10|15|20)$/, variants: ['dark'] },
    { pattern: /^text-(brand|success|error|warning|blue-light|orange|purple)-(400|500|600|700)$/, variants: ['dark'] },
    { pattern: /^bg-(brand|success|error|warning|blue-light|orange|purple)-(50|100)$/ },
    // Kanban: outlines de color por estado de proyecto (border-t/l, runtime).
    { pattern: /^border-(t|l)-(brand|success|error|warning|blue-light|orange|gray)-400$/ },
  ],
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./apps/**/forms.py",
    "./apps/**/views.py",
    // Hotfix S2b.1.5: las clases generadas dinámicamente en JS (dropdown de
    // referencias.js, ui.js) deben quedar en el CSS compilado.
    "./static/**/*.js",
    "./apps/**/static/**/*.js",
    "../referencias/static/**/*.js",
    "../interfono/static/**/*.js",
    // En Docker los shared apps se copian planos a /app/<app>/, así que el
    // mismo glob como sibling cubre el path real durante el build.
    "./referencias/static/**/*.js",
    "./interfono/static/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        inter: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'title-2xl': ['72px', { lineHeight: '90px' }],
        'title-xl':  ['60px', { lineHeight: '72px' }],
        'title-lg':  ['48px', { lineHeight: '60px' }],
        'title-md':  ['36px', { lineHeight: '44px' }],
        'title-sm':  ['30px', { lineHeight: '38px' }],
        'title-xs':  ['24px', { lineHeight: '32px' }],
        'theme-xl':  ['20px', { lineHeight: '30px' }],
        'theme-sm':  ['14px', { lineHeight: '20px' }],
        'theme-xs':  ['12px', { lineHeight: '18px' }],
      },
      colors: {
        // Sobrescribimos `gray` con la paleta de TailAdmin (es la canónica
        // del sistema visual). El sweep slate/stone→gray de S-TailAdmin-1
        // garantiza que solo esta paleta se use en templates.
        gray: {
          25:  '#fcfcfd',
          50:  '#f9fafb',
          100: '#f2f4f7',
          200: '#e4e7ec',
          300: '#d0d5dd',
          400: '#98a2b3',
          500: '#667085',
          600: '#475467',
          700: '#3f3f3f',
          800: '#272727',
          900: '#171717',
          950: '#111111',
          dark: '#212121',
        },
        brand: {
          25:  '#f2f7ff',
          50:  '#ecf3ff',
          100: '#dde9ff',
          200: '#c2d6ff',
          300: '#9cb9ff',
          400: '#7592ff',
          500: '#465fff',
          600: '#3641f5',
          700: '#2a31d8',
          800: '#252dae',
          900: '#262e89',
          950: '#161950',
        },
        'blue-light': {
          25:  '#f5fbff',
          50:  '#f0f9ff',
          100: '#e0f2fe',
          200: '#b9e6fe',
          300: '#7cd4fd',
          400: '#36bffa',
          500: '#0ba5ec',
          600: '#0086c9',
          700: '#026aa2',
          800: '#065986',
          900: '#0b4a6f',
          950: '#062c41',
        },
        success: {
          25:  '#f6fef9',
          50:  '#ecfdf3',
          100: '#d1fadf',
          200: '#a6f4c5',
          300: '#6ce9a6',
          400: '#32d583',
          500: '#12b76a',
          600: '#039855',
          700: '#027a48',
          800: '#05603a',
          900: '#054f31',
          950: '#053321',
        },
        error: {
          25:  '#fffbfa',
          50:  '#fef3f2',
          100: '#fee4e2',
          200: '#fecdca',
          300: '#fda29b',
          400: '#f97066',
          500: '#f04438',
          600: '#d92d20',
          700: '#b42318',
          800: '#912018',
          900: '#7a271a',
          950: '#55160c',
        },
        warning: {
          25:  '#fffcf5',
          50:  '#fffaeb',
          100: '#fef0c7',
          200: '#fedf89',
          300: '#fec84b',
          400: '#fdb022',
          500: '#f79009',
          600: '#dc6803',
          700: '#b54708',
          800: '#93370d',
          900: '#7a2e0e',
          950: '#4e1d09',
        },
        orange: {
          25:  '#fffaf5',
          50:  '#fff6ed',
          100: '#ffead5',
          200: '#fddcab',
          300: '#feb273',
          400: '#fd853a',
          500: '#fb6514',
          600: '#ec4a0a',
          700: '#c4320a',
          800: '#9c2a10',
          900: '#7e2410',
          950: '#511c10',
        },
      },
      boxShadow: {
        'theme-xs': '0 1px 2px 0 rgba(16, 24, 40, 0.05)',
        'theme-sm': '0 1px 3px 0 rgba(16, 24, 40, 0.1), 0 1px 2px 0 rgba(16, 24, 40, 0.06)',
        'theme-md': '0 4px 8px -2px rgba(16, 24, 40, 0.1), 0 2px 4px -2px rgba(16, 24, 40, 0.06)',
        'theme-lg': '0 12px 16px -4px rgba(16, 24, 40, 0.08), 0 4px 6px -2px rgba(16, 24, 40, 0.03)',
        'theme-xl': '0 20px 24px -4px rgba(16, 24, 40, 0.08), 0 8px 8px -4px rgba(16, 24, 40, 0.03)',
      },
    },
  },
  plugins: [],
};
