// El Interfono — flujo cliente: pedir permiso, registrar SW, suscribir,
// notificar al backend. Idempotente: si ya está suscrito, refresca el estado.
//
// Requiere en window:
//   _INTERFONO_VAPID_PUBLIC  → string base64url (puede ser '' si no configurado)
//   _INTERFONO_CSRF          → CSRF token cookie

(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const ESTADO = $('#interfono-estado');
  const BTN_ACTIVAR = $('#interfono-activar');
  const BTN_PRUEBA = $('#interfono-prueba');
  if (!ESTADO || !BTN_ACTIVAR) return;

  function mostrar(estado) {
    ESTADO.querySelectorAll('[data-cuando]').forEach((el) => {
      el.classList.toggle('hidden', el.dataset.cuando !== estado);
    });
    if (estado === 'suscrito' && BTN_PRUEBA) {
      BTN_PRUEBA.classList.remove('hidden');
      BTN_ACTIVAR.classList.add('hidden');
    }
  }

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = window.atob(base64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; ++i) out[i] = raw.charCodeAt(i);
    return out;
  }

  async function detectar() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      mostrar('no_soportado');
      return;
    }
    if (Notification.permission === 'denied') {
      mostrar('bloqueado');
      return;
    }
    const reg = await navigator.serviceWorker.getRegistration();
    if (!reg) {
      mostrar('no_suscrito');
      return;
    }
    const sub = await reg.pushManager.getSubscription();
    mostrar(sub ? 'suscrito' : 'no_suscrito');
  }

  async function activar() {
    if (!window._INTERFONO_VAPID_PUBLIC) {
      alert('Notificaciones no configuradas.');
      return;
    }
    BTN_ACTIVAR.disabled = true;
    try {
      const permiso = await Notification.requestPermission();
      if (permiso !== 'granted') {
        mostrar(permiso === 'denied' ? 'bloqueado' : 'no_suscrito');
        return;
      }
      const reg = await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(window._INTERFONO_VAPID_PUBLIC),
      });
      const payload = sub.toJSON();
      const resp = await fetch('/perfil/notificaciones/suscribir', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': window._INTERFONO_CSRF,
        },
        body: JSON.stringify({ endpoint: payload.endpoint, keys: payload.keys }),
      });
      if (!resp.ok) {
        alert('No fue posible registrar la suscripción.');
        return;
      }
      mostrar('suscrito');
    } catch (e) {
      console.error('interfono:', e);
      alert('Error al activar notificaciones: ' + (e && e.message ? e.message : e));
    } finally {
      BTN_ACTIVAR.disabled = false;
    }
  }

  async function prueba() {
    const resp = await fetch('/perfil/notificaciones/prueba', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': window._INTERFONO_CSRF },
    });
    if (!resp.ok) {
      alert('No se pudo enviar la prueba.');
      return;
    }
    const data = await resp.json();
    if (data.entregadas === 0 && data.fallidas === 0) {
      alert('Suscríbete primero en este navegador.');
    }
  }

  BTN_ACTIVAR.addEventListener('click', activar);
  if (BTN_PRUEBA) BTN_PRUEBA.addEventListener('click', prueba);
  detectar();
})();
