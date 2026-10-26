r"""Cancionero Caná — diagnóstico de lectura (no modifica Notion).

Uso:  .\.venv\Scripts\python.exe conexion_notion.py
Requiere NOTION_API_TOKEN en el archivo .env de esta carpeta.
"""
from pathlib import Path
import os
import sys
import unicodedata

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env'))
TOKEN = os.getenv('NOTION_API_TOKEN', '').strip()
BASE_URL = 'https://api.notion.com/v1'
API_VERSION = '2026-03-11'
SOURCE_NAME = 'Canciones Caná'


def normalized(text):
    """Compara títulos sin que afecten mayúsculas ni tildes."""
    text = unicodedata.normalize('NFKD', text.casefold())
    # Notion puede incluir emojis/iconos al comienzo del título, por ejemplo
    # '🎶 Canciones Caná'. Eliminamos símbolos y puntuación al comparar.
    plain = ''.join(
        c for c in text
        if not unicodedata.combining(c) and (c.isalnum() or c.isspace())
    )
    return ' '.join(plain.split())


def request(method, endpoint, *, params=None, json=None):
    try:
        response = requests.request(
            method,
            BASE_URL + endpoint,
            headers={
                'Authorization': f'Bearer {TOKEN}',
                'Notion-Version': API_VERSION,
                'Content-Type': 'application/json',
            },
            params=params,
            json=json,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as error:
        print(f'Error HTTP {error.response.status_code} al consultar Notion.')
        # Mensaje de error remoto, nunca imprimimos token ni cabeceras.
        try:
            print('Detalle:', error.response.json().get('message', 'Sin detalle'))
        except ValueError:
            print('No se pudo leer la respuesta del servidor.')
        if error.response.status_code in (403, 404):
            print('Revisa el acceso de "Cancionero Cana API" a la base original "Canciones Caná".')
        sys.exit(1)
    except requests.RequestException as error:
        print('No se pudo conectar con Notion:', type(error).__name__)
        sys.exit(1)


def visible_sources():
    """Lista fuentes reales disponibles a la conexión (no vistas enlazadas)."""
    sources = []
    cursor = None
    while True:
        payload = {'page_size': 100, 'filter': {'property': 'object', 'value': 'data_source'}}
        if cursor:
            payload['start_cursor'] = cursor
        result = request('POST', '/search', json=payload)
        sources.extend(result.get('results', []))
        if not result.get('has_more') or not result.get('next_cursor'):
            break
        cursor = result['next_cursor']
    return sources


def source_title(item):
    parts = item.get('title', [])
    if isinstance(parts, str):
        return parts
    return ''.join(part.get('plain_text', part.get('text', {}).get('content', '')) for part in parts)


def find_source():
    sources = visible_sources()
    print(f'Fuentes de datos visibles: {len(sources)}')
    for source in sources:
        print(' -', source_title(source) or '(sin título)')
    matches = [src for src in sources if normalized(source_title(src)) == normalized(SOURCE_NAME)]
    if len(matches) == 1:
        print(f'Base encontrada: {source_title(matches[0])}')
        return matches[0]['id']
    if len(matches) > 1:
        sys.exit('Hay varias fuentes con el mismo nombre. Será necesario especificar el ID.')
    sys.exit('La fuente esperada no coincide con los títulos mostrados arriba. Verifica el nombre de la base en Notion.')


def song_title(page):
    for prop in page.get('properties', {}).values():
        if prop.get('type') == 'title':
            return ''.join(t.get('plain_text', '') for t in prop.get('title', []))
    return '(sin nombre)'


def properties_text(page):
    values = []
    for name, prop in page.get('properties', {}).items():
        kind = prop.get('type')
        if kind in ('select', 'status') and prop.get(kind):
            values.append(f'{name}: {prop[kind]["name"]}')
        elif kind == 'multi_select':
            selections = [x['name'] for x in prop.get('multi_select', [])]
            if selections:
                values.append(f'{name}: {", ".join(selections)}')
    return ' | '.join(values)


def query_songs(source_id):
    rows = []
    cursor = None
    while True:
        payload = {'page_size': 100}
        if cursor:
            payload['start_cursor'] = cursor
        response = request('POST', f'/data_sources/{source_id}/query', json=payload)
        rows.extend(response.get('results', []))
        if not response.get('has_more') or not response.get('next_cursor'):
            break
        cursor = response['next_cursor']
    return rows


def read_first_chords(page_id):
    print('\nFragmentos amarillos detectados en la canción de prueba:')
    data = request('GET', f'/blocks/{page_id}/children', params={'page_size': 100})
    total = 0
    for block in data.get('results', []):
        kind = block.get('type', '')
        content = block.get(kind, {})
        for item in content.get('rich_text', []):
            content_text = item.get('plain_text', '').strip()
            color = item.get('annotations', {}).get('color')
            if color in ('yellow', 'yellow_background') and content_text:
                total += 1
                if total <= 12:
                    print(' [amarillo]', content_text[:100])
    if not total:
        print(' No se detectaron en los primeros 100 bloques. Revisaremos la estructura después.')
    print(f'Total en los primeros bloques: {total}')


def main():
    if not TOKEN:
        sys.exit('No encontré NOTION_API_TOKEN en el archivo .env de esta carpeta.')
    print('Cancionero Caná — prueba de conexión de solo lectura\n')
    source_id = find_source()
    songs = query_songs(source_id)
    print(f'\nCanciones recuperadas: {len(songs)}')
    for num, page in enumerate(songs, 1):
        print(f'{num}. {song_title(page)}')
        props = properties_text(page)
        if props:
            print('   ', props)
    if songs:
        preferred = next((s for s in songs if 'himno' in normalized(song_title(s))), songs[0])
        print(f'\nCanción para verificar acordes: {song_title(preferred)}')
        read_first_chords(preferred['id'])
    print('\nPrueba terminada. No se modificó ningún dato de Notion.')


if __name__ == '__main__':
    main()
