"""Búsqueda de títulos para el selector de Cancionero Caná.

Los títulos se muestran como están en Notion. Solo la comparación de texto
ignora tildes, mayúsculas y puntuación, reutilizando conexion_notion.normalized.
"""
from conexion_notion import normalized


def search_song_options(query, pages, title_func, limit=200):
    """Return [(original title, notion page ID)] for the dropdown."""
    query_norm = normalized(query or "")
    choices = []
    for page in pages:
        title = title_func(page)
        title_norm = normalized(title)
        if not query_norm or query_norm in title_norm:
            score = (0 if title_norm.startswith(query_norm) else 1, title_norm)
            choices.append((score, title, page["id"]))
    choices.sort(key=lambda entry: entry[0])
    return [(title, song_id) for _, title, song_id in choices[:limit]]
