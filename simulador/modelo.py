from __future__ import annotations

import logging
import math
from functools import lru_cache
import os
from pathlib import Path
from typing import Literal, Optional

import numpy as np

log = logging.getLogger("derrames")

# --------------------------------------------------------------------------
# Constantes del modelo (fijadas por la especificación)
# --------------------------------------------------------------------------
DT_S = 1800.0                 # Δt = 30 min
STEPS_PER_HOUR = int(3600 / DT_S)
C_D = 0.04                    # coeficiente de arrastre por viento
KH_DEFAULT = 1.0              # m²/s (configurable hasta KH_MAX)
KH_MAX = 10.0
M_ANCHOR, RHO_ANCHOR, M_MAX = 0.1, 200.0, 0.95
M_METERS_PER_DEG = 111000.0
NODATA_THRESHOLD = -9.0e8     # -9.99e+08 => NaN (nunca velocidad cero)

DENSIDADES = {"ligero": 830.0, "medio": 870.0, "pesado": 950.0}

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE / "data"))
WIND_FILE = DATA_DIR / "salidadatos.txt"
# dirmarea.txt (oleaje/marea): ver nota en `corriente_marina()`.
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"


def friccion_M(rho: float) -> float:
    """M = min(0.95, 0.1 · ρ/200)."""
    return min(M_MAX, M_ANCHOR * rho / RHO_ANCHOR)


# --------------------------------------------------------------------------
# Campo de viento (malla regular, serie temporal horaria)
# --------------------------------------------------------------------------
class WindField:
    """
    U, V: arrays [nt, ny, nx] en m/s (hacia dónde VA el viento: E y N positivos).
    Celdas sin dato -> NaN. Una celda NaN en t=0 se considera TIERRA.
    """

    def __init__(self, lons, lats, U, V, demo: bool = False):
        self.lons, self.lats = np.asarray(lons), np.asarray(lats)
        self.U, self.V = U, V
        self.nt, self.ny, self.nx = U.shape
        self.lon0, self.lat0 = self.lons[0], self.lats[0]
        self.dlon = float(np.median(np.diff(self.lons)))
        self.dlat = float(np.median(np.diff(self.lats)))
        self.land = np.isnan(U[0])          # máscara estática de tierra
        self.demo = demo

    # -- carga ------------------------------------------------------------
    @classmethod
    def from_file(cls, path: Path) -> "WindField":
        """
        SUPUESTO DE FORMATO (ajustar aquí si salidadatos.txt difiere):
        texto delimitado por espacios/comas, una fila por celda y tiempo:
            hora  lon  lat  U  V
        Líneas vacías o que empiecen con '#' se ignoran.
        """
        raw = np.genfromtxt(path, comments="#", delimiter=None, dtype=float)
        if raw.ndim != 2 or raw.shape[1] < 5:
            raise ValueError("salidadatos.txt: se esperan 5 columnas: hora lon lat U V")
        t, lon, lat, u, v = (raw[:, k] for k in range(5))
        u = np.where(u < NODATA_THRESHOLD, np.nan, u)
        v = np.where(v < NODATA_THRESHOLD, np.nan, v)

        ts, lons, lats = np.unique(t), np.unique(np.round(lon, 4)), np.unique(np.round(lat, 4))
        it = np.searchsorted(ts, t)
        ix = np.searchsorted(lons, np.round(lon, 4))
        iy = np.searchsorted(lats, np.round(lat, 4))
        U = np.full((len(ts), len(lats), len(lons)), np.nan)
        V = U.copy()
        U[it, iy, ix] = u
        V[it, iy, ix] = v
        log.info("Viento: %d tiempos, malla %dx%d", len(ts), len(lats), len(lons))
        return cls(lons, lats, U, V)

    @classmethod
    def demo(cls) -> "WindField":
        """SOLO PRUEBAS: viento uniforme 5 m/s hacia el NE, sin tierra. No son datos reales."""
        lons = np.arange(-95.0, -89.0 + 1e-9, 0.16)
        lats = np.arange(18.0, 22.5 + 1e-9, 0.16)
        shp = (121, len(lats), len(lons))
        return cls(lons, lats, np.full(shp, 3.5), np.full(shp, 3.5), demo=True)

    # -- muestreo ---------------------------------------------------------
    def _frac(self, lon, lat):
        return (lon - self.lon0) / self.dlon, (lat - self.lat0) / self.dlat

    def inside(self, lon, lat):
        fx, fy = self._frac(lon, lat)
        return (fx >= 0) & (fx <= self.nx - 1) & (fy >= 0) & (fy <= self.ny - 1)

    def is_land(self, lon, lat):
        """True si la celda más cercana es tierra (NaN)."""
        fx, fy = self._frac(lon, lat)
        i = np.clip(np.rint(fx).astype(int), 0, self.nx - 1)
        j = np.clip(np.rint(fy).astype(int), 0, self.ny - 1)
        return self.land[j, i]

    @staticmethod
    def _bilinear(field, fx, fy):
        ny, nx = field.shape
        i0 = np.clip(np.floor(fx).astype(int), 0, nx - 2)
        j0 = np.clip(np.floor(fy).astype(int), 0, ny - 2)
        wx, wy = np.clip(fx - i0, 0, 1), np.clip(fy - j0, 0, 1)
        bil = (field[j0, i0] * (1 - wx) * (1 - wy) + field[j0, i0 + 1] * wx * (1 - wy)
               + field[j0 + 1, i0] * (1 - wx) * wy + field[j0 + 1, i0 + 1] * wx * wy)
        near = field[np.clip(np.rint(fy).astype(int), 0, ny - 1),
                     np.clip(np.rint(fx).astype(int), 0, nx - 1)]
        # Si alguna esquina es NaN, se usa la celda más cercana (puede seguir NaN)
        return np.where(np.isnan(bil), near, bil)

    def sample(self, lon, lat, t_hours: float):
        """Viento (u, v) interpolado en espacio (bilineal) y tiempo (lineal)."""
        fx, fy = self._frac(lon, lat)
        tf = min(max(t_hours, 0.0), self.nt - 1)      # mantiene el último tiempo
        t0 = int(math.floor(tf))
        t1 = min(t0 + 1, self.nt - 1)
        w = tf - t0
        u = (1 - w) * self._bilinear(self.U[t0], fx, fy) + w * self._bilinear(self.U[t1], fx, fy)
        v = (1 - w) * self._bilinear(self.V[t0], fx, fy) + w * self._bilinear(self.V[t1], fx, fy)
        return u, v


def corriente_marina(lon, lat, t_hours: float):
    """
    u_sea (m/s). PUNTO ABIERTO: la especificación define dirmarea.txt como
    'dirección y altura de ola' pero NO una fórmula para convertirlos en velocidad
    de corriente, y no se debe inventar una. Hasta definirla, u_sea = 0.
    Para integrarla, reemplazar el cuerpo de esta función (devolver u, v en m/s).
    """
    z = np.zeros_like(lon)
    return z, z


# --------------------------------------------------------------------------
# Simulación
# --------------------------------------------------------------------------
def simular(wind: WindField, lat_ini: float, lon_ini: float, rho: float,
            horas: int, n: int, kh: float = KH_DEFAULT,
            sigma_deg: float = 0.01, seed: Optional[int] = None) -> dict:
    rng = np.random.default_rng(seed)
    M = friccion_M(rho)

    lat = lat_ini + rng.normal(0, sigma_deg, n)           # dispersión inicial
    lon = lon_ini + rng.normal(0, sigma_deg, n)
    activa = ~wind.is_land(lon, lat) & wind.inside(lon, lat)
    sigma_diff = math.sqrt(2.0 * kh * DT_S)                # m

    def snapshot(h):
        return {"hora": h, "particulas": [
            {"lat": round(float(a), 4), "lon": round(float(b), 4)} for a, b in zip(lat, lon)]}

    lista = [snapshot(0)]
    for step in range(horas * STEPS_PER_HOUR):
        t_h = step * DT_S / 3600.0
        uw, vw = wind.sample(lon, lat, t_h)
        us, vs = corriente_marina(lon, lat, t_h)
        R = rng.random(n)                                  # R ~ U(0,1)
        factor = (1.0 - R * M) * DT_S
        dx = (us + C_D * uw) * factor + rng.standard_normal(n) * sigma_diff   # m
        dy = (vs + C_D * vw) * factor + rng.standard_normal(n) * sigma_diff   # m

        nlat = lat + dy / M_METERS_PER_DEG
        nlon = lon + dx / (M_METERS_PER_DEG * np.cos(np.radians(lat)))

        # Adherencia a la costa: celda de tierra (NaN) o fuera del dominio => se detiene
        valida = wind.inside(nlon, nlat) & ~wind.is_land(nlon, nlat)
        mover = activa & valida
        lat = np.where(mover, nlat, lat)
        lon = np.where(mover, nlon, lon)
        activa = mover

        if (step + 1) % STEPS_PER_HOUR == 0:
            lista.append(snapshot((step + 1) // STEPS_PER_HOUR))
    return {"lista": lista}


# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_wind() -> Optional[WindField]:
    """Carga única por instancia (cold start). None si no hay datos."""
    if WIND_FILE.exists():
        return WindField.from_file(WIND_FILE)
    if DEMO_MODE:
        log.warning("DEMO_MODE: viento sintético uniforme, SIN datos reales.")
        return WindField.demo()
    log.error("No existe %s (use DEMO_MODE=1 solo para pruebas).", WIND_FILE)
    return None
