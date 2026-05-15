from django.http import JsonResponse
from django.shortcuts import render


def proximamente(request):
    return render(request, "proximamente.html")


def buzon_proximamente(request):
    return render(request, "buzon_proximamente.html")


def ping(request):
    return JsonResponse({"ok": True, "app": "la-recepcion", "estado": "stub"})
