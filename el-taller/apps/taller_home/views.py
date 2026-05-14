from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render


@login_required
def home(request):
    """Home de El Taller. S1b llenará con La Cartera, Los Proyectos, El Pizarrón."""
    return render(request, "taller_home/home.html")


def ping(request):
    return JsonResponse({"ok": True, "app": "el-taller"})
