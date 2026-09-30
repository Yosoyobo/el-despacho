/* La Salchicha — easter egg de los campos de texto de El Taller.
 *
 * LC 2026-09-30 (Oscar): escribir «hotdog» en cualquier campo de texto
 * (buscadores, formularios, la caja de El Chalán) lo vuelve una salchicha
 * dentro de su pan; al borrarlo regresa a la normalidad. Es un easter egg: NO
 * va en Novedades, en el manual ni en El Chalán.
 *
 * Todo vive aquí (estilos incluidos) para no tocar `input.css`. Escucha por
 * delegación, así que alcanza también a los campos que llegan por HTMX.
 */
(function () {
    'use strict';

    var PALABRAS = { hotdog: 1, hotdogs: 1, perrocaliente: 1, perroscalientes: 1 };

    // Nunca contraseñas: sólo lo que se escribe a la vista.
    var CAMPOS = 'textarea, input:not([type]), input[type="text"], input[type="search"], ' +
        'input[type="email"], input[type="url"], input[type="tel"]';

    var CSS = [
        '.salchicha{',
        '  color:#fff!important;caret-color:#fff;border-color:transparent!important;',
        '  border-radius:9999px!important;text-shadow:0 1px 1px rgba(60,15,0,.45);',
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
        '  animation:salchicha-brinca .5s cubic-bezier(.3,1.6,.5,1);',
        '}',
        // Una caja de varias líneas no cabe en una píldora: las esquinas se comerían el texto.
        'textarea.salchicha{border-radius:1.75rem!important;padding-left:1.1rem!important;padding-right:1.1rem!important}',
        '.salchicha::placeholder{color:rgba(255,236,224,.8)!important}',
        '.salchicha::-webkit-search-cancel-button{filter:brightness(0) invert(1)}',
        '@keyframes salchicha-brinca{',
        '  0%{transform:scale(1)}35%{transform:scale(1.04,.9)}',
        '  65%{transform:scale(.98,1.05)}100%{transform:scale(1)}',
        '}',
        '@media (prefers-reduced-motion:reduce){.salchicha{animation:none}}'
    ].join('\n');

    function esSalchicha(valor) {
        var v = (valor || '').toLowerCase().normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '').replace(/[\s\-_.]/g, '');
        return PALABRAS.hasOwnProperty(v);
    }

    function revisar(campo) {
        var si = esSalchicha(campo.value);
        if (si && !document.getElementById('salchicha-estilos')) {
            var s = document.createElement('style');
            s.id = 'salchicha-estilos';
            s.textContent = CSS;
            document.head.appendChild(s);
        }
        campo.classList.toggle('salchicha', si);
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

    // Un campo que llega ya con «hotdog» (?q=hotdog) también se vuelve salchicha.
    function escanear(raiz) {
        (raiz || document).querySelectorAll(CAMPOS).forEach(function (c) {
            if (c.value) revisar(c);
        });
    }
    document.addEventListener('DOMContentLoaded', function () { escanear(); });
    document.addEventListener('htmx:afterSwap', function (e) { escanear(e.target); });

    // El Chalán (y cualquier formulario) vacía la caja por código al enviar, sin
    // disparar `input`: la salchicha se quedaría con la caja ya vacía.
    function desenfundar() {
        setTimeout(function () {
            document.querySelectorAll('.salchicha').forEach(revisar);
        }, 60);
    }
    ['htmx:afterRequest', 'reset', 'submit'].forEach(function (ev) {
        document.addEventListener(ev, desenfundar, true);
    });
})();
