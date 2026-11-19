"""Pruebas de los datos de Claude y Codex (con archivos de ejemplo, sin internet)."""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

import ia


def test_cuanto_falta():
    ahora = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    assert ia.cuanto_falta(ahora + timedelta(hours=2, minutes=10), ahora) == "2 h 10 min"
    assert ia.cuanto_falta(ahora + timedelta(minutes=35), ahora) == "35 min"
    assert ia.cuanto_falta(ahora + timedelta(days=3, hours=4), ahora) == "3 d 4 h"
    assert ia.cuanto_falta(ahora - timedelta(minutes=1), ahora) == ""
    assert ia.cuanto_falta(None) == ""


def test_formato_tokens():
    assert ia.formato_tokens(950) == "950"
    assert ia.formato_tokens(1234) == "1,2 mil"
    assert ia.formato_tokens(2_500_000) == "2,5 M"


def test_interpretar_limites_claude():
    respuesta = {
        "five_hour": {"utilization": 42.0, "resets_at": "2026-11-18T20:00:00+00:00"},
        "seven_day": {"utilization": 18.5, "resets_at": "2026-11-22T10:00:00Z"},
        "seven_day_opus": None,
    }
    r = ia.interpretar_limites_claude(respuesta)
    assert r["sesion"]["porcentaje"] == 42.0
    assert r["semana"]["porcentaje"] == 18.5
    assert r["sesion"]["renueva"].hour == 20
    assert r["semana_opus"] is None


def test_limites_claude_sin_datos():
    with pytest.raises(ia.SinDatos):
        ia.interpretar_limites_claude({"five_hour": None, "seven_day": None})


def test_token_claude(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    with pytest.raises(ia.SinDatos, match="Instala Claude Code"):
        ia.token_claude()
    vence_futuro = (datetime.now().timestamp() + 3600) * 1000
    (tmp_path / ".credentials.json").write_text(json.dumps(
        {"claudeAiOauth": {"accessToken": "secreto", "expiresAt": vence_futuro}}))
    assert ia.token_claude() == "secreto"
    (tmp_path / ".credentials.json").write_text(json.dumps(
        {"claudeAiOauth": {"accessToken": "viejo", "expiresAt": 1000}}))
    with pytest.raises(ia.SinDatos, match="renovar"):
        ia.token_claude()


def _linea_claude(id_mensaje, momento, entrada, salida, cache_lectura=0, pedido="r1"):
    return json.dumps({
        "type": "assistant", "requestId": pedido, "timestamp": momento.isoformat(),
        "message": {"id": id_mensaje, "model": "claude", "usage": {
            "input_tokens": entrada, "output_tokens": salida,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": cache_lectura}},
    })


def test_tokens_claude_hoy(tmp_path):
    hoy = datetime.now().astimezone()
    ayer = hoy - timedelta(days=1)
    proyecto = tmp_path / "projects" / "mi-proyecto"
    proyecto.mkdir(parents=True)
    lineas = [
        _linea_claude("m1", hoy, 100, 50, 1000),
        _linea_claude("m1", hoy, 100, 50, 1000),          # repetida: se cuenta una vez
        _linea_claude("m2", hoy, 10, 5, pedido="r2"),
        _linea_claude("m3", ayer, 9999, 9999, pedido="r3"),  # de ayer: no cuenta
        '{"type": "user", "message": {"content": "hola"}}',
        "esto no es json {",
    ]
    (proyecto / "sesion.jsonl").write_text("\n".join(lineas), encoding="utf-8")
    total = ia.tokens_claude_hoy(tmp_path / "projects")
    assert total["mensajes"] == 2
    assert total["entrada"] == 110 and total["salida"] == 55 and total["cache_lectura"] == 1000
    assert total["total"] == 110 + 55 + 1000


def test_tokens_claude_sin_carpeta(tmp_path):
    with pytest.raises(ia.SinDatos):
        ia.tokens_claude_hoy(tmp_path / "no-existe")


def _evento_codex(primario, secundario, renueva):
    return json.dumps({"timestamp": "2026-11-18T12:00:00Z", "type": "event_msg", "payload": {
        "type": "token_count", "info": None, "rate_limits": {
            "primary": {"used_percent": primario, "window_minutes": 300, "resets_at": renueva},
            "secondary": {"used_percent": secundario, "window_minutes": 10080, "resets_at": renueva + 86400}}}})


def test_limites_codex(tmp_path):
    futuro = int(datetime.now(timezone.utc).timestamp()) + 3600
    dia = tmp_path / "2026" / "11" / "18"
    dia.mkdir(parents=True)
    viejo = dia / "rollout-a.jsonl"
    viejo.write_text(_evento_codex(10, 5, futuro), encoding="utf-8")
    nuevo = dia / "rollout-b.jsonl"
    nuevo.write_text("\n".join([_evento_codex(30, 12, futuro), '{"type": "otro"}', _evento_codex(65, 31, futuro)]),
                     encoding="utf-8")
    os.utime(viejo, (1, 1))   # que el "viejo" sea más antiguo
    r = ia.limites_codex(tmp_path)
    assert r["sesion"]["porcentaje"] == 65 and r["semana"]["porcentaje"] == 31
    assert r["sesion"]["minutos"] == 300


def test_codex_ventana_vencida_es_cero():
    pasado = int(datetime.now(timezone.utc).timestamp()) - 60
    r = ia.interpretar_linea_codex(_evento_codex(80, 40, pasado))
    assert r["sesion"]["porcentaje"] == 0.0


def _credenciales(carpeta, vence_en_segundos, token="nuevo"):
    vence = (datetime.now().timestamp() + vence_en_segundos) * 1000
    (carpeta / ".credentials.json").write_text(json.dumps(
        {"claudeAiOauth": {"accessToken": token, "expiresAt": vence}}))


def test_renovar_sesion_claude(tmp_path, monkeypatch):
    """Si la sesión venció, mibarra le pide a Claude Code (sin ventana) que la renueve."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    _credenciales(tmp_path, -60, "viejo")
    llamadas = []

    def claude_falso(orden, **kw):
        llamadas.append(orden)
        _credenciales(tmp_path, 8 * 3600)          # lo que hace Claude Code al renovar

    monkeypatch.setattr(ia, "ruta_claude_code", lambda: "claude.exe")
    monkeypatch.setattr(ia.subprocess, "run", claude_falso)
    monkeypatch.setattr(ia, "_ultimo_intento", 0.0)
    assert ia.renovar_sesion_claude() is True
    assert llamadas[0][:3] == ["claude.exe", "-p", "ok"]
    assert ia.token_claude() == "nuevo"
    # No lo intenta de nuevo enseguida (máximo una vez cada 20 min)
    _credenciales(tmp_path, -60, "viejo")
    assert ia.renovar_sesion_claude() is False
    assert len(llamadas) == 1


def test_renovar_sin_claude_code(monkeypatch):
    monkeypatch.setattr(ia, "ruta_claude_code", lambda: None)
    assert ia.renovar_sesion_claude(forzar=True) is False


def test_limites_claude_renueva_y_reintenta(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    _credenciales(tmp_path, -60, "viejo")
    monkeypatch.setattr(ia, "renovar_sesion_claude", lambda: _credenciales(tmp_path, 3600) or True)
    usados = []

    class Respuesta:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, *a): return json.dumps({"five_hour": {"utilization": 30, "resets_at": None},
                                               "seven_day": {"utilization": 10, "resets_at": None}}).encode()

    def abrir_url(pedido, timeout):
        usados.append(pedido.get_header("Authorization"))
        return Respuesta()

    monkeypatch.setattr(ia.urllib.request, "urlopen", abrir_url)
    datos = ia.limites_claude()
    assert usados == ["Bearer nuevo"]
    assert datos["sesion"]["porcentaje"] == 30


def test_limites_claude_vencida_sin_poder_renovar(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    _credenciales(tmp_path, -60, "viejo")
    monkeypatch.setattr(ia, "renovar_sesion_claude", lambda: False)
    with pytest.raises(ia.SinDatos, match="clic para renovar"):
        ia.limites_claude()
