/* El Arrastre — motor único de arrastrar y soltar de El Taller.
 *
 * LC 2026-08-12 (Oscar): «Tenemos varios formatos de arrastrables en la
 * plataforma, unificar». Había SEIS implementaciones en dos tecnologías: el
 * tablero de proyectos, el de tareas, el calendario y los KPIs usaban el drag
 * & drop de HTML5, que **no existe en pantalla táctil** — por eso desde el
 * celular las tarjetas no se movían. Aquí queda una sola, con Pointer Events,
 * que funciona igual con el dedo y con el ratón.
 *
 * Contrato por atributos (se escanea al cargar y en cada `htmx:afterSwap`):
 *
 *   <div data-arr-zona data-arr-grupo="tareas"
 *        data-arr-orden-url="/tareas/reordenar"        (opcional)
 *        data-arr-mover-url="/tareas/{id}/cambiar-estado"  (opcional)
 *        data-arr-mover-campo="estado" data-arr-mover-valor="en_proceso"
 *        data-arr-eje="y|xy">
 *     <article data-arr-item="12">
 *       <button data-arr-asa>⠿</button>   (opcional; sin asa arrastra todo)
 *     </article>
 *   </div>
 *
 * Dos zonas se intercambian elementos sólo si comparten `data-arr-grupo`.
 * En `data-arr-mover-url`, `{id}` se sustituye por el `data-arr-item`.
 *
 * Eventos (burbujean; `preventDefault()` cancela el POST que hace el motor):
 *   arrastrar:ordenar  detail {zona, ids}            — cambió el orden
 *   arrastrar:mover    detail {zona, origen, id, elemento} — cambió de zona
 *
 * Distinguir un clic de un arrastre: no pasa nada hasta recorrer UMBRAL px, así
 * que las tarjetas que son enlaces siguen abriéndose al picarlas.
 *
 * Y con el DEDO, en un elemento sin asa, hay que **mantener presionado**
 * (LC 2026-08-13, Oscar: «no me deja scrollear a gusto por la página, agarra
 * tareas y las arrastra»). Deslizar scrollea; sostener levanta la tarjeta —
 * el gesto que ya usa cualquier teléfono. Con asa no aplica: agarrar un blanco
 * de 20px dedicado a eso ya es intención explícita.
 */
(function () {
    'use strict';

    var UMBRAL = 6;        // px antes de considerar que es un arrastre
    var BORDE = 72;        // px de orilla donde la página empieza a rodar sola
    var PASO = 14;         // px por cuadro al rodar

    // Con el DEDO, en un elemento SIN asa, hay que mantener presionado para
    // agarrarlo (LC 2026-08-13, Oscar: «no me deja scrollear a gusto por la
    // página, agarra tareas y las arrastra»). Deslizar scrollea; sostener
    // levanta la tarjeta — el gesto que ya usa cualquier teléfono. Con asa no
    // aplica: agarrarla ya es intención explícita.
    var ESPERA_TACTIL = 320;   // ms sosteniendo antes de que agarre
    var TOLERANCIA = 10;       // px que se pueden mover sin cancelar la espera

    var item = null;       // elemento que se arrastra
    var zonaOrigen = null;
    var asa = null;
    var punteroId = null;
    var x0 = 0, y0 = 0;
    var activo = false;    // ya se está arrastrando de verdad
    var esperando = null;  // timer del «mantén presionado»
    var rodando = null;

    function zonaDe(el) { return el && el.closest ? el.closest('[data-arr-zona]') : null; }
    function grupoDe(z) { return z ? (z.getAttribute('data-arr-grupo') || '') : null; }

    // Una zona puede acotar qué recibe con `data-arr-acepta="item,otro"`, contra
    // el `data-arr-tipo` del elemento. Sin el atributo, acepta todo. (Es lo que
    // impide meter una carpeta del menú dentro de otra carpeta.)
    function acepta(zona, el) {
        var lista = zona.getAttribute('data-arr-acepta');
        if (!lista) return true;
        var tipo = el.getAttribute('data-arr-tipo') || '';
        return lista.split(',').some(function (t) { return t.trim() === tipo; });
    }

    function itemsDe(zona) {
        // Sólo los hijos directos en zonas anidadas (carpetas del menú): un
        // `querySelectorAll` se llevaría también los de la zona de adentro.
        return Array.prototype.filter.call(
            zona.querySelectorAll('[data-arr-item]'),
            function (el) { return zonaDe(el.parentElement) === zona; }
        );
    }

    function csrf() {
        var i = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (i && i.value) return i.value;
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    function postear(url, pares) {
        var cuerpo = new URLSearchParams();
        pares.forEach(function (p) { cuerpo.append(p[0], p[1]); });
        return fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrf(),
                'Content-Type': 'application/x-www-form-urlencoded',
                'HX-Request': 'true'
            },
            body: cuerpo,
            credentials: 'same-origin'
        });
    }

    /* ── Acomodo mientras arrastras ─────────────────────────────────────── */

    function reacomodar(zona, x, y) {
        var otros = itemsDe(zona).filter(function (el) { return el !== item; });
        var eje = zona.getAttribute('data-arr-eje') || 'y';
        var destino = null;

        if (eje === 'xy') {
            // Rejillas (KPIs, calendario): manda el más cercano al puntero.
            var mejor = Infinity;
            otros.forEach(function (el) {
                var r = el.getBoundingClientRect();
                var cx = r.left + r.width / 2, cy = r.top + r.height / 2;
                var d = (x - cx) * (x - cx) + (y - cy) * (y - cy);
                if (d < mejor) { mejor = d; destino = (x < cx || (x === cx && y < cy)) ? el : el.nextElementSibling; }
            });
        } else {
            for (var i = 0; i < otros.length; i++) {
                var b = otros[i].getBoundingClientRect();
                if (y < b.top + b.height / 2) { destino = otros[i]; break; }
            }
        }
        if (destino && destino.parentElement === zona) zona.insertBefore(item, destino);
        else zona.appendChild(item);
    }

    function resaltar(zona) {
        document.querySelectorAll('[data-arr-zona]').forEach(function (z) {
            z.classList.toggle('ring-2', z === zona);
            z.classList.toggle('ring-brand-400', z === zona);
        });
    }

    // El «Sin proyectos» de una columna vacía estorba en cuanto le cae algo.
    function pintarVacios() {
        document.querySelectorAll('[data-arr-zona]').forEach(function (z) {
            var v = z.querySelector('[data-arr-vacio]');
            if (v) v.classList.toggle('hidden', itemsDe(z).length > 0);
        });
    }

    function rodarSiHaceFalta(y) {
        var alto = window.innerHeight;
        var d = 0;
        if (y < BORDE) d = -PASO;
        else if (y > alto - BORDE) d = PASO;
        if (!d) { detenerRodado(); return; }
        if (rodando) return;
        rodando = setInterval(function () { window.scrollBy(0, d); }, 16);
    }
    function detenerRodado() { if (rodando) { clearInterval(rodando); rodando = null; } }

    /* ── Persistencia ───────────────────────────────────────────────────── */

    function avisar(nombre, zona, detalle) {
        var ev = new CustomEvent('arrastrar:' + nombre, {
            bubbles: true, cancelable: true, detail: detalle
        });
        zona.dispatchEvent(ev);
        return !ev.defaultPrevented;
    }

    function guardarOrden(zona) {
        var ids = itemsDe(zona)
            .map(function (el) { return el.getAttribute('data-arr-item'); })
            .filter(Boolean);
        if (!avisar('ordenar', zona, { zona: zona, ids: ids })) return;
        var url = zona.getAttribute('data-arr-orden-url');
        if (!url || !ids.length) return;
        var campo = zona.getAttribute('data-arr-orden-campo') || 'orden';
        postear(url, ids.map(function (id) { return [campo, id]; }))
            .catch(function () { /* el acomodo ya se ve; un refresh lo corrige */ });
    }

    function mover(zona, origen, elemento, alTerminar) {
        var id = elemento.getAttribute('data-arr-item');
        if (!avisar('mover', zona, { zona: zona, origen: origen, id: id, elemento: elemento })) {
            alTerminar(true);
            return;
        }
        var url = zona.getAttribute('data-arr-mover-url');
        if (!url) { alTerminar(true); return; }
        var campo = zona.getAttribute('data-arr-mover-campo') || 'valor';
        var valor = zona.getAttribute('data-arr-mover-valor') || '';
        var pares = [[campo, valor]];
        // Campos extra que pida la vista, tipo `hx_kanban=1&otro=2`.
        var extra = zona.getAttribute('data-arr-mover-extra') || '';
        new URLSearchParams(extra).forEach(function (v, k) { pares.push([k, v]); });
        postear(url.replace('{id}', encodeURIComponent(id)), pares)
            .then(function (r) {
                var ok = r.ok || r.status === 204 || r.status === 302;
                if (ok) {
                    zona.dispatchEvent(new CustomEvent('arrastrar:movido', {
                        bubbles: true,
                        detail: { zona: zona, origen: origen, id: id, elemento: elemento, respuesta: r }
                    }));
                }
                alTerminar(ok, r);
            })
            .catch(function () { alTerminar(false); });
    }

    /* ── Gesto ──────────────────────────────────────────────────────────── */

    function arrancableDesde(destino) {
        // Con asa: sólo el asa. Sin asa: todo el elemento, salvo los controles
        // y los enlaces/botones de ADENTRO (el elemento mismo sí puede serlo).
        var a = destino.closest('[data-arr-asa]');
        if (a) return a.closest('[data-arr-item]');
        var el = destino.closest('[data-arr-item]');
        if (!el || el.querySelector('[data-arr-asa]')) return null;
        if (destino.closest('input, select, textarea, label')) return null;
        var clic = destino.closest('a, button');
        if (clic && clic !== el && el.contains(clic)) return null;
        return el;
    }

    function agarrar() {
        if (!item || activo) return;
        activo = true;
        esperando = null;
        try { asa.setPointerCapture(punteroId); } catch (_) {}
        item.classList.add('opacity-50');
        document.body.classList.add('select-none');
        // Un tirón corto avisa que ya quedó agarrada — sin él, en el celular no
        // se sabe si el «mantén presionado» prendió.
        if (navigator.vibrate) { try { navigator.vibrate(12); } catch (_) {} }
    }

    function cancelarEspera() {
        if (esperando) { clearTimeout(esperando); esperando = null; }
    }

    document.addEventListener('pointerdown', function (e) {
        if (e.button > 0 || !e.target.closest) return;
        var el = arrancableDesde(e.target);
        if (!el) return;
        var zona = zonaDe(el.parentElement);
        if (!zona) return;
        item = el; zonaOrigen = zona; punteroId = e.pointerId;
        asa = e.target.closest('[data-arr-asa]') || el;
        x0 = e.clientX; y0 = e.clientY; activo = false;
        cancelarEspera();
        // Con el dedo y sin asa: hay que SOSTENER. Mientras tanto no se toca el
        // gesto, así que la página scrollea como siempre; si el dedo se mueve
        // antes de tiempo, era scroll y se cancela.
        if (e.pointerType !== 'mouse' && !e.target.closest('[data-arr-asa]')) {
            esperando = setTimeout(agarrar, ESPERA_TACTIL);
        }
    });

    document.addEventListener('pointermove', function (e) {
        if (!item || e.pointerId !== punteroId) return;
        if (esperando) {
            // Se movió mientras esperábamos: era una deslizada para scrollear.
            if (Math.abs(e.clientX - x0) > TOLERANCIA || Math.abs(e.clientY - y0) > TOLERANCIA) {
                cancelarEspera();
                item = null; zonaOrigen = null; punteroId = null; asa = null;
            }
            return;   // sin `preventDefault`: la página se mueve con normalidad
        }
        if (!activo) {
            if (Math.abs(e.clientX - x0) < UMBRAL && Math.abs(e.clientY - y0) < UMBRAL) return;
            agarrar();
        }
        e.preventDefault();
        rodarSiHaceFalta(e.clientY);

        // Para saber sobre qué zona vamos, el elemento arrastrado tiene que
        // dejar de estorbarle al puntero.
        item.style.pointerEvents = 'none';
        var bajo = document.elementFromPoint(e.clientX, e.clientY);
        item.style.pointerEvents = '';
        var zona = zonaDe(bajo) || zonaOrigen;
        if (grupoDe(zona) !== grupoDe(zonaOrigen)) zona = zonaOrigen;
        // Ni a una zona que no lo acepta, ni dentro de sí mismo.
        if (!acepta(zona, item) || item.contains(zona)) zona = zonaOrigen;
        resaltar(zona);
        reacomodar(zona, e.clientX, e.clientY);
        pintarVacios();
    });

    function soltar(e) {
        if (!item || (e && e.pointerId !== punteroId)) return;
        cancelarEspera();
        var el = item, origen = zonaOrigen, hubo = activo;
        item = null; zonaOrigen = null; punteroId = null; activo = false;
        detenerRodado();
        el.classList.remove('opacity-50');
        document.body.classList.remove('select-none');
        resaltar(null);
        if (asa) { try { asa.releasePointerCapture(e.pointerId); } catch (_) {} asa = null; }
        if (!hubo) return;   // fue un clic: que siga su camino

        // Tras un arrastre real, el clic que viene detrás no debe abrir nada.
        document.addEventListener('click', function tragar(ev) {
            ev.preventDefault(); ev.stopPropagation();
        }, { capture: true, once: true });

        var zona = zonaDe(el.parentElement);
        if (!zona) return;
        if (zona === origen) { guardarOrden(zona); return; }
        mover(zona, origen, el, function (ok) {
            if (!ok) {
                origen.appendChild(el);
                alert('No se pudo mover. Recarga la página.');
                return;
            }
            guardarOrden(zona);
            if (origen !== zona) guardarOrden(origen);
        });
    }

    document.addEventListener('pointerup', soltar);
    document.addEventListener('pointercancel', soltar);

    // En ESCRITORIO, los enlaces y las imágenes son arrastrables de fábrica: al
    // mover el ratón sobre una tarjeta que es un `<a>` —el tablero de Tareas, el
    // de Proyectos, el calendario— el navegador arranca SU PROPIO arrastre (el
    // fantasma con el título y la URL), manda `pointercancel` y el nuestro
    // muere antes de agarrar nada. Con el dedo no pasa, porque el arrastre
    // nativo no existe en táctil: por eso el tablero se movía en el celular y
    // no en la computadora (LC 2026-08-13, Oscar).
    document.addEventListener('dragstart', function (e) {
        if (e.target.closest && e.target.closest('[data-arr-item]')) e.preventDefault();
    }, true);

    // Mientras se arrastra de verdad, la página no debe moverse. `preventDefault`
    // en `pointermove` no lo garantiza: el scroll táctil sólo se frena desde
    // `touchmove` con el listener NO pasivo. Y sólo con `activo`, para que
    // deslizar sobre una tarjeta siga scrolleando (LC 2026-08-13).
    document.addEventListener('touchmove', function (e) {
        if (activo) e.preventDefault();
    }, { passive: false });

    // El ASA no scrollea nunca: es un blanco chiquito dedicado a arrastrar.
    // El resto del elemento SÍ, porque si no, deslizar sobre una tarjeta del
    // tablero se comía el scroll de toda la página — ése era el bug. Ahí el
    // gesto es «mantén presionado» (ver `ESPERA_TACTIL`).
    function marcar() {
        document.querySelectorAll('[data-arr-item]').forEach(function (el) {
            // Cinturón y tirantes contra el arrastre nativo (ver el `dragstart`
            // de arriba): así el navegador ni siquiera lo intenta.
            el.setAttribute('draggable', 'false');
            var a = el.querySelector('[data-arr-asa]');
            if (a) a.classList.add('touch-none');
            // `select-none`: sin él, sostener el dedo sobre una tarjeta saca el
            // globo de «copiar / buscar» de iOS en vez de agarrarla.
            else el.classList.add('cursor-grab', 'active:cursor-grabbing', 'select-none');
        });
        pintarVacios();
    }
    document.addEventListener('DOMContentLoaded', marcar);
    document.body && marcar();
    document.addEventListener('htmx:afterSwap', marcar);
})();
