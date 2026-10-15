import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import modelo

LIMITES = {"lat": (18.0, 22.5), "lon": (-95.0, -89.0), "horas": (1, 240),
           "n": (1, 800), "kh": (0.0, modelo.KH_MAX)}  # n<=800: Vercel limita la respuesta a ~4.5 MB


def _num(request, nombre, defecto, tipo, minimo, maximo):
    raw = request.GET.get(nombre, defecto)
    try:
        v = tipo(raw)
    except (TypeError, ValueError):
        raise ValueError(f"'{nombre}' inválido")
    if not (minimo <= v <= maximo):
        raise ValueError(f"'{nombre}' debe estar entre {minimo} y {maximo}")
    return v


@require_GET
def index(request):
    return render(request, "simulador/index.html")


@require_GET
def simular(request):
    wind = modelo.get_wind()
    if wind is None:
        return JsonResponse({"detail": "Campo de viento no disponible: falta data/salidadatos.txt"}, status=503)
    try:
        lat = _num(request, "lat_ini", 19.85, float, *LIMITES["lat"])
        lon = _num(request, "lon_ini", -90.55, float, *LIMITES["lon"])
        horas = _num(request, "horas", 120, int, *LIMITES["horas"])
        n = _num(request, "n_particulas", 200, int, *LIMITES["n"])
        kh = _num(request, "kh", modelo.KH_DEFAULT, float, 1e-6, LIMITES["kh"][1])
        seed = request.GET.get("seed")
        seed = int(seed) if seed not in (None, "") else None
    except ValueError as e:
        return JsonResponse({"detail": str(e)}, status=422)
    tipo = request.GET.get("tipo_crudo", "medio")
    if tipo not in modelo.DENSIDADES:
        return JsonResponse({"detail": "tipo_crudo debe ser ligero, medio o pesado"}, status=422)

    data = modelo.simular(wind, lat, lon, modelo.DENSIDADES[tipo], horas, n, kh, seed=seed)
    return HttpResponse(json.dumps(data, separators=(",", ":")), content_type="application/json")


@require_GET
def salud(request):
    w = modelo.get_wind()
    return JsonResponse({"viento_cargado": w is not None, "demo": bool(w and w.demo)})
