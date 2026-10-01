/* Los Antojos — easter egg de los campos de texto de El Taller.
 *
 * LC 2026-09-30 (Oscar): escribir una palabra mágica en cualquier campo de texto
 * (buscadores, formularios, la caja de El Chalán) lo vuelve antojo:
 *   «hotdog» → salchicha dentro de su pan
 *   «donut»  → éclair con el glaseado rosa y las chispas de la dona de los Simpson
 *   «trump»  → Modo YUGE (LC 2026-10-01, Oscar): la página dorada, letras enormes
 *              y «Make Learning Center Great Again»; el campo dorado con el retrato oficial
 *              adentro y el copete rubio encima. Sin video (Oscar lo quitó).
 * El antojo se queda aunque se borre el texto, hasta recargar la página. Es un
 * easter egg: NO va en Novedades, en el manual ni en El Chalán.
 *
 * Todo vive aquí (estilos incluidos) para no tocar `input.css`. Escucha por
 * delegación, así que alcanza también a los campos que llegan por HTMX.
 */
(function () {
    'use strict';

    var PALABRAS = {
        hotdog: 'salchicha', hotdogs: 'salchicha', perrocaliente: 'salchicha', perroscalientes: 'salchicha',
        donut: 'eclair', donuts: 'eclair', doughnut: 'eclair', doughnuts: 'eclair', dona: 'eclair', donas: 'eclair',
        trump: 'trump', donaldtrump: 'trump', yuge: 'trump'
    };
    var CLASES = ['salchicha', 'eclair', 'trump'];

    // Retrato oficial (dominio público, obra del gobierno de EE. UU., vía Wikimedia),
    // vendoreado en static; la URL llega del `{% static %}` del <script>.
    var RETRATO = (document.currentScript && document.currentScript.dataset.retrato) || '';
    var COPETE = '<svg viewBox="0 0 200 90" xmlns="http://www.w3.org/2000/svg">' +
        '<defs><linearGradient id="copete-oro" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0" stop-color="#fff3bf"/><stop offset=".45" stop-color="#f2cf6b"/>' +
        '<stop offset="1" stop-color="#cf952a"/></linearGradient></defs>' +
        '<path fill="url(#copete-oro)" stroke="#b9821f" stroke-width="1.5" d="M6 84C8 52 40 24 92 16C130 10 170 14 194 30' +
        'C178 26 160 27 146 32C168 36 186 48 192 62C172 50 146 46 120 50C136 56 146 66 148 78' +
        'C120 64 80 62 48 70C30 74 16 80 6 84Z"/>' +
        '<g fill="none" stroke="#c48a22" stroke-width="2" stroke-linecap="round" opacity=".6">' +
        '<path d="M30 66C60 40 110 26 170 26"/><path d="M50 70C80 52 120 42 176 46"/>' +
        '<path d="M24 58C56 30 100 20 150 20"/></g>' +
        '<path d="M40 50C70 32 110 24 150 22" fill="none" stroke="#fffbe6" stroke-width="3" ' +
        'stroke-linecap="round" opacity=".75"/></svg>';

    // Nunca contraseñas: sólo lo que se escribe a la vista.
    var CAMPOS = 'textarea, input:not([type]), input[type="text"], input[type="search"], ' +
        'input[type="email"], input[type="url"], input[type="tel"]';

    // Chispas de la dona: 16 barritas de colores giradas al azar, en mosaico.
    // El pan va ENCIMA de ellas (transparente arriba) para que sólo se vean en el glaseado.
    var CHISPAS = 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'96\' height=\'36\'%3E%3Crect x=\'29.3\' y=\'7.1\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%23fff\' transform=\'rotate(101 32.5 8.2)\'/%3E%3Crect x=\'58.1\' y=\'4.9\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%232f9bff\' transform=\'rotate(124 61.3 6.0)\'/%3E%3Crect x=\'48.0\' y=\'13.1\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%23ffd21f\' transform=\'rotate(41 51.2 14.2)\'/%3E%3Crect x=\'5.9\' y=\'17.1\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%2335c759\' transform=\'rotate(170 9.1 18.2)\'/%3E%3Crect x=\'6.9\' y=\'5.4\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%23ff3b30\' transform=\'rotate(57 10.1 6.5)\'/%3E%3Crect x=\'38.2\' y=\'26.1\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%238e5cff\' transform=\'rotate(41 41.4 27.2)\'/%3E%3Crect x=\'56.0\' y=\'29.4\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%23ff9f0a\' transform=\'rotate(110 59.2 30.5)\'/%3E%3Crect x=\'86.7\' y=\'4.2\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%23fff\' transform=\'rotate(131 89.9 5.3)\'/%3E%3Crect x=\'76.3\' y=\'11.0\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%232f9bff\' transform=\'rotate(103 79.5 12.1)\'/%3E%3Crect x=\'16.7\' y=\'19.2\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%23ffd21f\' transform=\'rotate(86 19.9 20.3)\'/%3E%3Crect x=\'28.4\' y=\'19.3\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%2335c759\' transform=\'rotate(107 31.6 20.4)\'/%3E%3Crect x=\'70.7\' y=\'22.5\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%23ff3b30\' transform=\'rotate(50 73.9 23.6)\'/%3E%3Crect x=\'84.7\' y=\'22.2\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%238e5cff\' transform=\'rotate(91 87.9 23.3)\'/%3E%3Crect x=\'3.0\' y=\'27.4\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%23ff9f0a\' transform=\'rotate(81 6.2 28.5)\'/%3E%3Crect x=\'18.1\' y=\'8.6\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%23fff\' transform=\'rotate(23 21.3 9.7)\'/%3E%3Crect x=\'20.1\' y=\'29.6\' width=\'6.4\' height=\'2.2\' rx=\'1.1\' fill=\'%232f9bff\' transform=\'rotate(93 23.3 30.7)\'/%3E%3C/svg%3E")';

    var CSS = [
        '.salchicha,.eclair,.trump{',
        '  border-color:transparent!important;border-radius:9999px!important;',
        '  animation:antojo-brinca .5s cubic-bezier(.3,1.6,.5,1);',
        '}',
        // Una caja de varias líneas no cabe en una píldora: las esquinas se comerían el texto.
        'textarea.salchicha,textarea.eclair,textarea.trump{border-radius:1.75rem!important;padding-left:1.1rem!important;padding-right:1.1rem!important}',

        '.salchicha{',
        '  color:#fff!important;caret-color:#fff;text-shadow:0 1px 1px rgba(60,15,0,.45);',
        '  background:',
        '    radial-gradient(110% 55% at 50% 22%,rgba(255,214,184,.55),rgba(255,214,184,0) 48%),',
        '    radial-gradient(circle at 30% 40%,rgba(255,255,255,.07) 0 1px,transparent 1.6px) 0 0/7px 5px,',
        '    radial-gradient(circle at 70% 70%,rgba(90,20,0,.12) 0 1px,transparent 1.6px) 0 0/9px 6px,',
        '    linear-gradient(180deg,#e2693c 0%,#cf4b23 34%,#b53b18 70%,#8a2a10 100%)!important;',
        '  box-shadow:',
        '    inset 14px 0 14px -10px rgba(70,15,0,.6),inset -14px 0 14px -10px rgba(70,15,0,.6),',
        '    inset 0 -4px 6px rgba(70,15,0,.35),',
        '    0 3px 5px rgba(70,25,0,.4),',
        '    0 0 0 4px #f5e0b5,',
        '    0 -9px 0 8px #e0a55b,',
        '    0 9px 0 8px #c58640,',
        '    0 12px 18px 8px rgba(0,0,0,.18)!important;',
        '}',
        '.salchicha::placeholder{color:rgba(255,236,224,.8)!important}',
        '.salchicha::-webkit-search-cancel-button{filter:brightness(0) invert(1)}',

        // El éclair: pan dorado abajo, glaseado rosa arriba con escurridos y chispas.
        '.eclair{',
        '  color:#4a1530!important;caret-color:#4a1530;text-shadow:0 1px 0 rgba(255,255,255,.45);',
        '  background:',
        '    radial-gradient(90% 38% at 50% 14%,rgba(255,255,255,.6),rgba(255,255,255,0) 60%),',
        '    radial-gradient(7px 6px at 50% 0,#f07aaf 96%,transparent) 0 100%/22px 38% repeat-x,',
        '    radial-gradient(4px 10px at 50% 0,#f07aaf 96%,transparent) 9px 100%/37px 38% repeat-x,',
        '    linear-gradient(180deg,transparent 62%,#d49249 62%,#a9682d 85%,#7d491c 100%),',
        '    ' + CHISPAS + ' 0 0/96px 36px,',
        '    linear-gradient(180deg,#fbb3d4 0%,#f07aaf 62%)!important;',
        '  background-clip:padding-box!important;',
        '  box-shadow:',
        '    inset 12px 0 12px -9px rgba(90,45,10,.5),inset -12px 0 12px -9px rgba(90,45,10,.5),',
        '    inset 0 -3px 5px rgba(90,45,10,.4),',
        '    0 4px 8px rgba(90,45,10,.35),',
        '    0 10px 16px rgba(0,0,0,.12)!important;',
        '}',
        '.eclair::placeholder{color:rgba(74,21,48,.6)!important}',

        // «trump»: el campo con marco dorado, el retrato en hilera y el texto encima.
        '.trump{',
        // Por encima de la capa dorada del Modo YUGE, para que el retrato salga a color.
        '  position:relative;z-index:99985;',
        '  color:#fff!important;caret-color:#ffd700;font-weight:700!important;',
        '  text-shadow:0 1px 2px #000,0 0 6px rgba(0,0,0,.7);',
        '  background:',
        '    linear-gradient(90deg,rgba(40,25,0,.7),rgba(40,25,0,.35) 40%,rgba(40,25,0,.1)),',
        "    url('" + RETRATO + "') 0 22%/auto 240% repeat-x,",
        '    linear-gradient(135deg,#8a6a12,#f7e08a 30%,#c9a227 55%,#fff1b0 75%,#a07d1c)!important;',
        '  background-clip:padding-box!important;',
        '  box-shadow:0 0 0 3px #d4af37,0 0 0 5px #fff3b0,0 0 0 6px #a07d1c,0 0 22px 6px rgba(212,175,55,.55)!important;',
        '}',
        '.trump::placeholder{color:rgba(255,248,220,.85)!important}',
        '.copete-trump{position:fixed;left:0;top:0;z-index:99990;pointer-events:none;',
        '  filter:drop-shadow(0 3px 3px rgba(80,50,0,.35));animation:antojo-brinca .6s cubic-bezier(.3,1.6,.5,1)}',
        '.copete-trump svg{display:block;width:100%;height:auto}',

        // Modo YUGE: toda la página dorada (una capa con mix-blend-mode, que no mueve
        // nada del layout), letras enormes y el titular.
        'html.yuge{font-size:130%!important}',
        'html.yuge iframe[data-marco]{z-index:99985}',
        '#yuge-dorado{position:fixed;inset:0;z-index:99980;pointer-events:none;mix-blend-mode:color;',
        '  background:linear-gradient(135deg,#b8860b,#ffd700 40%,#daa520 60%,#fff2a8 80%,#b8860b);',
        '  background-size:300% 300%;animation:yuge-brillo 6s ease-in-out infinite alternate}',
        '@keyframes yuge-brillo{0%{background-position:0% 50%}100%{background-position:100% 50%}}',
        '#yuge-titular{margin:0 0 1.5rem;text-align:center;text-transform:uppercase;letter-spacing:-.02em;',
        "  font:900 clamp(2.2rem,7vw,5.5rem)/1.05 Georgia,'Times New Roman',serif;",
        '  background:linear-gradient(180deg,#fff6c9,#f5c518 45%,#a8770e);-webkit-background-clip:text;background-clip:text;',
        '  color:transparent;filter:drop-shadow(0 3px 0 #6b4b05) drop-shadow(0 8px 14px rgba(0,0,0,.35));',
        '  animation:antojo-brinca .6s cubic-bezier(.3,1.6,.5,1)}',

        '@keyframes antojo-brinca{',
        '  0%{transform:scale(1)}35%{transform:scale(1.04,.9)}',
        '  65%{transform:scale(.98,1.05)}100%{transform:scale(1)}',
        '}',
        '@media (prefers-reduced-motion:reduce){.salchicha,.eclair,.trump,.copete-trump,#yuge-dorado,#yuge-titular{animation:none}}'
    ].join('\n');

    function antojoDe(valor) {
        var v = (valor || '').toLowerCase().normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '').replace(/[\s\-_.]/g, '');
        return PALABRAS.hasOwnProperty(v) ? PALABRAS[v] : null;
    }

    // Sólo pone: el antojo nunca se quita, ni al borrar ni al enviar (hasta recargar).
    // Una palabra nueva sí lo cambia por el otro antojo.
    function revisar(campo) {
        var clase = antojoDe(campo.value);
        if (!clase || campo.classList.contains(clase)) return;
        estilos(document);
        campo.classList.remove.apply(campo.classList, CLASES);
        campo.classList.add(clase);
        if (clase === 'trump') { modoYuge(); copete(campo); }
    }

    var TITULO = 'Make Learning Center Great Again';

    function estilos(doc) {
        if (doc.getElementById('antojos-estilos')) return;
        var s = doc.createElement('style');
        s.id = 'antojos-estilos';
        s.textContent = CSS;
        doc.head.appendChild(s);
    }

    // Dentro de una pestaña (marco de /pestanas/) la página es el contenedor: el
    // dorado, las letras y el título también van allá, no sólo en el marco.
    function documentosYuge() {
        var docs = [document];
        try {
            if (window.self !== window.top && window.top.location.origin === location.origin) {
                docs.push(window.top.document);
            }
        } catch (e) {}
        return docs;
    }

    function modoYuge() {
        documentosYuge().forEach(function (doc) {
            estilos(doc);
            var html = doc.documentElement;
            if (!html.classList.contains('yuge')) {
                html.classList.add('yuge');
                var capa = doc.createElement('div');
                capa.id = 'yuge-dorado';
                doc.body.appendChild(capa);
            }
            doc.title = TITULO;
        });
        if (!document.getElementById('yuge-titular')) {
            var main = document.querySelector('main') || document.body;
            var h = document.createElement('div');
            h.id = 'yuge-titular';
            h.textContent = TITULO;
            main.insertBefore(h, main.firstChild);
        }
    }

    // El copete no cabe dentro de un <input>: vive en <body> y sigue al campo en
    // cada cuadro (scroll, modales, cambios de tamaño). Se va si el campo se va
    // o cambia de antojo.
    var conCopete = [];
    function copete(campo) {
        if (campo.__copete) return;
        var el = document.createElement('div');
        el.className = 'copete-trump';
        el.innerHTML = COPETE;
        document.body.appendChild(el);
        campo.__copete = el;
        conCopete.push(campo);
        if (conCopete.length === 1) requestAnimationFrame(seguirCopetes);
    }
    function seguirCopetes() {
        conCopete = conCopete.filter(function (c) {
            var el = c.__copete;
            if (!c.isConnected || !c.classList.contains('trump')) {
                el.remove();
                c.__copete = null;
                return false;
            }
            var r = c.getBoundingClientRect();
            var w = Math.min(160, Math.max(70, r.width * 0.3));
            el.style.display = (r.width && r.height) ? '' : 'none';
            el.style.width = w + 'px';
            el.style.transform = 'translate(' + (r.left + Math.min(24, r.width * 0.06)) + 'px,' +
                (r.top - w * 0.45 * 0.93 + 3) + 'px)';
            return true;
        });
        if (conCopete.length) requestAnimationFrame(seguirCopetes);
    }

    function esCampo(el) {
        return el && el.matches && el.matches(CAMPOS);
    }

    // Mientras se compone una letra (acentos, ñ) no se toca nada: se revisa al terminarla.
    document.addEventListener('input', function (e) {
        if (esCampo(e.target) && !e.isComposing) revisar(e.target);
    });
    document.addEventListener('compositionend', function (e) {
        if (esCampo(e.target)) revisar(e.target);
    });

    // Un campo que llega ya con la palabra (?q=hotdog) también se vuelve antojo.
    function escanear(raiz) {
        (raiz || document).querySelectorAll(CAMPOS).forEach(function (c) {
            if (c.value) revisar(c);
        });
    }
    document.addEventListener('DOMContentLoaded', function () { escanear(); });
    document.addEventListener('htmx:afterSwap', function (e) {
        escanear(e.target);
        if (document.documentElement.classList.contains('yuge')) modoYuge();
    });
})();
