"""Custom handlers para 404/500 que renderizan templates con link al Buzón."""

from django.shortcuts import render


def handler404(request, exception=None):
    return render(request, "errores/404.html", status=404)


def handler500(request):
    return render(request, "errores/500.html", status=500)
