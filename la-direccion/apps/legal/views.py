from django.shortcuts import render


def privacidad(request):
    return render(request, "legal/privacidad.html")


def terminos(request):
    return render(request, "legal/terminos.html")
