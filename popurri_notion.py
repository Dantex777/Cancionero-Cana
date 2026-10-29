"""Persistencia opcional de popurrís en una FUENTE SEPARADA de Notion.

No modifica Canciones Caná. La escritura requiere token exclusivo y clave
de administración del servidor. No expone esos valores al navegador.
Configuración en Streamlit Secrets:
  NOTION_POPURRIS_SOURCE_ID = "uuid-de-fuente"
  NOTION_POPURRIS_TOKEN = "ntn_token_de_integracion_separada"
  POPURRIS_ADMIN_PASSWORD = "clave-larga-exclusiva"
La fuente debe tener propiedades: Nombre (title), Datos (rich_text).
"""
import json
import os
import requests

API_ROOT = "https://api.notion.com/v1"
API_VERSION = "2026-03-11"
MAX_ITEMS = 30


class PopurriNotionError(RuntimeError):
    pass


def setting(st, key: str) -> str:
    try:
        return str(st.secrets.get(key) or os.getenv(key, "")).strip()
    except (FileNotFoundError, KeyError, AttributeError):
        return str(os.getenv(key, "")).strip()


def configured(st) -> bool:
    return bool(setting(st, "NOTION_POPURRIS_SOURCE_ID") and
                setting(st, "NOTION_POPURRIS_TOKEN"))


def _request(st, method: str, path: str, payload=None):
    token = setting(st, "NOTION_POPURRIS_TOKEN")
    if not token:
        raise PopurriNotionError("Falta la credencial de Popurrís en Streamlit Secrets.")
    try:
        response = requests.request(
            method, API_ROOT + path, json=payload, timeout=25,
            headers={"Authorization": "Bearer " + token,
                     "Notion-Version": API_VERSION,
                     "Content-Type": "application/json"})
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        raise PopurriNotionError(
            f"Notion respondió HTTP {status}. Revisa la fuente, "
            "sus propiedades y los permisos de la integración.") from None
    except requests.RequestException:
        raise PopurriNotionError("No fue posible contactar la base de Popurrís.") from None


def _source_id(st):
    source = setting(st, "NOTION_POPURRIS_SOURCE_ID")
    if not source:
        raise PopurriNotionError("Falta NOTION_POPURRIS_SOURCE_ID.")
    return source


def validate_payload(data: dict, valid_ids: set[str]) -> dict:
    if not isinstance(data, dict) or data.get("format") != "cana-popurri-v1":
        raise ValueError("El formato no corresponde a un popurrí de Caná.")
    rows = data.get("songs", [])
    if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
        raise ValueError("El popurrí tiene una cantidad de canciones inválida.")
    clean = []
    for row in rows:
        if not isinstance(row, dict) or row.get("song_id") not in valid_ids:
            continue
        clean.append({"song_id": row["song_id"],
                      "steps": max(-24, min(24, int(row.get("steps", 0))))})
    if not clean:
        raise ValueError("El popurrí no contiene canciones disponibles.")
    return {
        "format": "cana-popurri-v1",
        "name": str(data.get("name") or "Popurrí")[:100],
        "mode": "Personalizado",
        "target": str(data.get("target") or "Bm")[:4],
        "songs": clean,
    }


def list_saved(st, valid_ids: set[str]) -> list[dict]:
    cursor = None
    items = []
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = _request(st, "POST",
                        f"/data_sources/{_source_id(st)}/query", body)
        for page in data.get("results", []):
            props = page.get("properties", {})
            try:
                content = "".join(
                    item.get("plain_text", item.get("text", {}).get("content", ""))
                    for item in props.get("Datos", {}).get("rich_text", []))
                parsed = validate_payload(json.loads(content), valid_ids)
            except (TypeError, ValueError, AttributeError, KeyError):
                continue
            items.append({"id": page["id"], "name": parsed["name"],
                          "data": parsed})
        cursor = data.get("next_cursor")
        if not data.get("has_more") or not cursor or len(items) >= 300:
            break
    return items


def create_saved(st, data: dict, valid_ids: set[str]) -> str:
    clean = validate_payload(data, valid_ids)
    serialized = json.dumps(clean, ensure_ascii=False, separators=(",", ":"))
    # Notion limita el contenido de cada fragmento de rich_text a 2000 caracteres.
    chunks = [serialized[i:i+1800] for i in range(0, len(serialized), 1800)]
    if len(chunks) > 20:
        raise PopurriNotionError("El repertorio es demasiado grande para guardar.")
    payload = {
        "parent": {"type": "data_source_id", "data_source_id": _source_id(st)},
        "properties": {
            "Nombre": {"title": [{"text": {"content": clean["name"]}}]},
            "Datos": {"rich_text": [
                {"text": {"content": chunk}} for chunk in chunks
            ]},
        },
    }
    result = _request(st, "POST", "/pages", payload)
    return result.get("url", "")
