/* El Checador por actividad (2026-10-01).
 *
 * Sólo se carga para quien tiene «Checador por actividad» prendido en El
 * Directorio. La jornada la arma el servidor con la actividad; aquí sólo se
 * toma la UBICACIÓN, para medirla contra las sedes como una checada:
 *
 * - con la primera pantalla del día el navegador pide permiso (la primera vez);
 * - después se vuelve a tomar en silencio, a lo más cada 10 minutos, para que
 *   la última actividad del día lleve la suya (es la de la salida);
 * - si la niega, no se insiste: la jornada cuenta igual, marcada sin ubicación.
 *
 * El envío va marcado como sondeo: la pantalla que lo cargó ya contó como
 * actividad.
 */
(function () {
    var s = document.currentScript;
    var url = s && s.dataset.url;
    var csrf = s && s.dataset.csrf;
    if (!url || !navigator.geolocation) return;

    var CLAVE = "despacho-checador-geo";
    var CADA_MS = 10 * 60 * 1000;
    var hoy = new Date().toLocaleDateString("en-CA");  // AAAA-MM-DD local

    var previo = null;
    try { previo = JSON.parse(localStorage.getItem(CLAVE) || "null"); } catch (e) { previo = null; }
    if (previo && previo.dia === hoy && Date.now() - previo.t < CADA_MS) return;

    function anotar() {
        try { localStorage.setItem(CLAVE, JSON.stringify({ dia: hoy, t: Date.now() })); } catch (e) { /* sin almacenamiento */ }
    }

    navigator.geolocation.getCurrentPosition(function (pos) {
        anotar();
        fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrf,
                "X-Despacho-Sondeo": "1"
            },
            body: JSON.stringify({
                lat: pos.coords.latitude,
                lng: pos.coords.longitude,
                precision: pos.coords.accuracy
            })
        }).catch(function () { /* se reintenta en la siguiente pantalla */ });
    }, function () {
        anotar();  // negada o sin señal: no insistir en cada pantalla
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 5 * 60 * 1000 });
})();
