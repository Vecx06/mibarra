"""
ia.py — de dónde sacamos el uso de Claude y de ChatGPT/Codex.

Todo lo de aquí es "lógica pura" (sin ventanas), así se puede probar fácil.

1) Límites del plan de Claude (sesión de 5 horas y semana):
   Claude Code guarda tu sesión en ~/.claude/.credentials.json. Con ese permiso le preguntamos
   a Anthropic (api.anthropic.com/api/oauth/usage) cuánto llevas usado. Es lo mismo que muestra
   claude.ai › Ajustes › Uso. El permiso NUNCA se guarda ni se anota en ningún lado: solo se usa
   para esa consulta, y solo se envía a Anthropic.

   Ese permiso dura unas 8 horas y SOLO Claude Code lo renueva (cuando lo usas). Si vence,
   mibarra abre Claude Code a escondidas con una pregunta mínima ("ok", con el modelo más
   barato) para que renueve la sesión solo. Como máximo una vez cada 20 minutos.

2) Tokens de Claude Code hoy:
   Claude Code anota cada respuesta en ~/.claude/projects/**/*.jsonl, con los tokens usados.
   Los sumamos sin conectarnos a nada.

3) Límites de Codex (ChatGPT):
   Codex anota en ~/.codex/sessions/AAAA/MM/DD/rollout-*.jsonl eventos "token_count" con
   "rate_limits" (porcentaje usado de la ventana de 5 horas y de la semana). Tampoco usa internet.
"""

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from version import VERSION


VENCIDA = "Sesión vencida · clic para renovar"


class SinDatos(Exception):
    """No hay datos (no está instalado, no hay sesión, etc.). El mensaje se muestra al usuario."""


# =============================================================================
# Utilidades de tiempo
# =============================================================================
def a_fecha(valor):
    """Convierte '2026-11-18T23:00:00Z', '...+00:00' o un número (segundos epoch) en datetime con zona."""
    if valor in (None, ""):
        return None
    if isinstance(valor, (int, float)):
        return datetime.fromtimestamp(valor, tz=timezone.utc)
    texto = str(valor).replace("Z", "+00:00")
    try:
        fecha = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def cuanto_falta(fecha, ahora=None):
    """datetime -> '2 h 10 min', '35 min', '3 d 4 h'. None o ya pasó -> ''."""
    if fecha is None:
        return ""
    ahora = ahora or datetime.now(timezone.utc)
    segundos = int((fecha - ahora).total_seconds())
    if segundos <= 0:
        return ""
    minutos = segundos // 60
    dias, resto = divmod(minutos, 60 * 24)
    horas, minutos = divmod(resto, 60)
    if dias:
        return f"{dias} d {horas} h"
    if horas:
        return f"{horas} h {minutos} min"
    return f"{max(minutos, 1)} min"


def formato_tokens(n):
    """1234 -> '1,2 mil' ; 2500000 -> '2,5 M'"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} M".replace(".", ",")
    if n >= 1_000:
        return f"{n / 1_000:.1f} mil".replace(".", ",")
    return str(int(n))


# =============================================================================
# 1) Límites del plan de Claude
# =============================================================================
def carpeta_claude():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))


def token_claude():
    """El permiso de Claude Code. Lanza SinDatos con una explicación si no hay."""
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return os.environ["CLAUDE_CODE_OAUTH_TOKEN"]
    archivo = carpeta_claude() / ".credentials.json"
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SinDatos("Instala Claude Code e inicia sesión") from None
    except (OSError, ValueError):
        raise SinDatos("No pude leer la sesión de Claude Code") from None
    oauth = datos.get("claudeAiOauth") or {}
    token = oauth.get("accessToken")
    if not token:
        raise SinDatos("Inicia sesión en Claude Code")
    vence = oauth.get("expiresAt")
    if isinstance(vence, (int, float)) and vence / 1000 < time.time():
        raise SinDatos(VENCIDA)
    return token


def ruta_claude_code():
    """Dónde está el programa claude (Claude Code). None si no está instalado."""
    encontrado = shutil.which("claude")
    if encontrado:
        return encontrado
    casa = Path.home()
    candidatos = [casa / ".local" / "bin" / "claude.exe", casa / ".local" / "bin" / "claude"]
    if os.environ.get("APPDATA"):
        candidatos.append(Path(os.environ["APPDATA"]) / "npm" / "claude.cmd")
    for candidato in candidatos:
        if candidato.exists():
            return str(candidato)
    return None


_SIN_VENTANA = 0x08000000      # CREATE_NO_WINDOW: que no aparezca una consola negra
_NUEVA_CONSOLA = 0x00000010    # CREATE_NEW_CONSOLE
_ultimo_intento = 0.0
ESPERA_ENTRE_INTENTOS = 20 * 60


def renovar_sesion_claude(forzar=False):
    """
    Pide a Claude Code (sin ventana) que renueve la sesión. Devuelve True si quedó renovada.
    Usa una pregunta mínima con el modelo más barato: gasta casi nada de tu plan.
    """
    global _ultimo_intento
    programa = ruta_claude_code()
    if not programa:
        return False
    if not forzar and time.monotonic() - _ultimo_intento < ESPERA_ENTRE_INTENTOS and _ultimo_intento:
        return False
    _ultimo_intento = time.monotonic()
    try:
        subprocess.run([programa, "-p", "ok", "--model", "haiku"], cwd=str(Path.home()),
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=120, creationflags=_SIN_VENTANA if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError):
        return False
    try:
        token_claude()
        return True
    except SinDatos:
        return False


def abrir_claude_code():
    """Plan B: abre Claude Code en una ventana para que el usuario inicie sesión o la renueve."""
    programa = ruta_claude_code()
    if not programa:
        return False
    try:
        subprocess.Popen([programa], cwd=str(Path.home()),
                         creationflags=_NUEVA_CONSOLA if os.name == "nt" else 0)
        return True
    except OSError:
        return False


def interpretar_limites_claude(datos):
    """Convierte la respuesta de Anthropic en algo simple para la barra."""
    def ventana(clave):
        v = datos.get(clave) or {}
        if v.get("utilization") is None:
            return None
        return {"porcentaje": float(v["utilization"]), "renueva": a_fecha(v.get("resets_at"))}

    resultado = {"sesion": ventana("five_hour"), "semana": ventana("seven_day"),
                 "semana_opus": ventana("seven_day_opus"), "semana_sonnet": ventana("seven_day_sonnet")}
    if resultado["sesion"] is None and resultado["semana"] is None:
        raise SinDatos("Tu cuenta no tiene límites de plan (¿usas la API?)")
    return resultado


def limites_claude(_reintento=True):
    try:
        token = token_claude()
    except SinDatos as aviso:
        if str(aviso) == VENCIDA and _reintento and renovar_sesion_claude():
            return limites_claude(_reintento=False)
        raise
    pedido = urllib.request.Request("https://api.anthropic.com/api/oauth/usage", headers={
        "Authorization": f"Bearer {token}",
        "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": f"mibarra/{VERSION}",
    })
    try:
        with urllib.request.urlopen(pedido, timeout=10) as respuesta:
            datos = json.load(respuesta)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            if _reintento and renovar_sesion_claude():
                return limites_claude(_reintento=False)
            raise SinDatos(VENCIDA) from None
        if error.code == 429:
            raise SinDatos("Anthropic pidió esperar un poco") from None
        raise
    return interpretar_limites_claude(datos)


# =============================================================================
# 2) Tokens de Claude Code hoy
# =============================================================================
_cache_archivos = {}


def _sumar_archivo(ruta, dia):
    """Suma los tokens de UN archivo de Claude Code para un día (fecha local). Devuelve dict + ids vistos."""
    total = {"entrada": 0, "salida": 0, "cache_escritura": 0, "cache_lectura": 0, "mensajes": 0}
    vistos = set()
    try:
        with open(ruta, encoding="utf-8", errors="ignore") as archivo:
            for linea in archivo:
                if '"usage"' not in linea:
                    continue
                try:
                    entrada = json.loads(linea)
                except ValueError:
                    continue
                mensaje = entrada.get("message")
                if not isinstance(mensaje, dict) or not isinstance(mensaje.get("usage"), dict):
                    continue
                fecha = a_fecha(entrada.get("timestamp"))
                if fecha is None or fecha.astimezone().date() != dia:
                    continue
                # La misma respuesta puede aparecer varias veces: la contamos una sola vez
                clave = f"{mensaje.get('id')}:{entrada.get('requestId')}"
                if clave in vistos:
                    continue
                vistos.add(clave)
                uso = mensaje["usage"]
                total["entrada"] += int(uso.get("input_tokens") or 0)
                total["salida"] += int(uso.get("output_tokens") or 0)
                total["cache_escritura"] += int(uso.get("cache_creation_input_tokens") or 0)
                total["cache_lectura"] += int(uso.get("cache_read_input_tokens") or 0)
                total["mensajes"] += 1
    except OSError:
        pass
    return total, vistos


def tokens_claude_hoy(carpeta=None, dia=None):
    carpeta = Path(carpeta) if carpeta else carpeta_claude() / "projects"
    if not carpeta.exists():
        raise SinDatos("No encontré Claude Code en este PC")
    dia = dia or datetime.now().date()
    inicio_dia = datetime.combine(dia, datetime.min.time()).timestamp()
    total = {"entrada": 0, "salida": 0, "cache_escritura": 0, "cache_lectura": 0, "mensajes": 0}
    vistos = set()
    for ruta in carpeta.rglob("*.jsonl"):
        try:
            estado = ruta.stat()
        except OSError:
            continue
        if estado.st_mtime < inicio_dia:          # no se tocó hoy: no puede tener mensajes de hoy
            continue
        clave = (str(ruta), estado.st_mtime, estado.st_size, dia)
        if clave not in _cache_archivos:
            _cache_archivos[clave] = _sumar_archivo(ruta, dia)
        parcial, ids = _cache_archivos[clave]
        repetidos = ids & vistos
        vistos |= ids
        if repetidos:   # muy raro: el mismo mensaje en dos archivos; recontamos sin repetir
            parcial, _ = _sumar_archivo(ruta, dia)
        for k in total:
            total[k] += parcial[k]
    total["total"] = total["entrada"] + total["salida"] + total["cache_escritura"] + total["cache_lectura"]
    if len(_cache_archivos) > 2000:
        _cache_archivos.clear()
    return total


# =============================================================================
# 3) Límites de Codex (ChatGPT)
# =============================================================================
def carpeta_codex():
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "sessions"


def _ventana_codex(datos, ahora):
    if not isinstance(datos, dict) or datos.get("used_percent") is None:
        return None
    renueva = a_fecha(datos.get("resets_at"))
    if renueva is None and datos.get("resets_in_seconds") is not None:
        renueva = None   # formato antiguo: sin hora exacta
    porcentaje = float(datos["used_percent"])
    if renueva is not None and renueva <= ahora:
        porcentaje = 0.0                       # esa ventana ya se renovó
    return {"porcentaje": porcentaje, "renueva": renueva, "minutos": datos.get("window_minutes")}


def interpretar_linea_codex(linea, ahora=None):
    """Si la línea es un evento token_count con rate_limits, devuelve los límites; si no, None."""
    if "rate_limits" not in linea:
        return None
    try:
        entrada = json.loads(linea)
    except ValueError:
        return None
    carga = entrada.get("payload") or {}
    if carga.get("type") != "token_count" or not isinstance(carga.get("rate_limits"), dict):
        return None
    ahora = ahora or datetime.now(timezone.utc)
    limites = carga["rate_limits"]
    resultado = {"sesion": _ventana_codex(limites.get("primary"), ahora),
                 "semana": _ventana_codex(limites.get("secondary"), ahora),
                 "fecha": a_fecha(entrada.get("timestamp"))}
    if resultado["sesion"] is None and resultado["semana"] is None:
        return None
    return resultado


def limites_codex(carpeta=None):
    carpeta = Path(carpeta) if carpeta else carpeta_codex()
    if not carpeta.exists():
        raise SinDatos("No encontré Codex en este PC")
    archivos = sorted(carpeta.rglob("rollout-*.jsonl"), key=lambda r: r.stat().st_mtime, reverse=True)
    for ruta in archivos[:10]:                   # el dato más nuevo está en los archivos más nuevos
        try:
            lineas = ruta.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for linea in reversed(lineas):
            resultado = interpretar_linea_codex(linea)
            if resultado:
                return resultado
    raise SinDatos("Usa Codex una vez para ver tus límites")
