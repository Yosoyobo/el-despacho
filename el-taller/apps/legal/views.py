from django.shortcuts import render


def privacidad(request):
    return render(request, "legal/privacidad.html")


def terminos(request):
    return render(request, "legal/terminos.html")


def acerca(request):
    """Página pública que explica qué es la app.

    Es la "Application home page" del cliente OAuth: la verificación de Google
    exige que describa el propósito de la aplicación, y el sitio de marketing
    describe los servicios de Learning Center, no este sistema. Se monta en la
    raíz (`/acerca/`), NO bajo `legal/`, para que sea una URL de portada.
    Pública a propósito: sin login, o Google no la puede leer.
    """
    return render(request, "legal/acerca.html")
