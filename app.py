"""Cancionero Caná v0.3.2: visor de solo lectura para canciones de Notion."""
from pathlib import Path
import os
import sys

import streamlit as st
from dotenv import load_dotenv

from musica import CSS, music_from_blocks, render_song, pitch_class, PREFERRED

st.set_page_config(page_title='Cancionero Caná', page_icon='🎶', layout='wide',
                   initial_sidebar_state='expanded')

# Se usa la misma .env y el mismo módulo de conexión que funcionó en PowerShell.
load_dotenv(Path(__file__).with_name('.env'))
try:
    if not os.getenv('NOTION_API_TOKEN') and st.secrets.get('NOTION_API_TOKEN'):
        os.environ['NOTION_API_TOKEN'] = st.secrets['NOTION_API_TOKEN']
except (FileNotFoundError, KeyError):
    pass

import conexion_notion as api  # noqa: E402


@st.cache_data(ttl=90, show_spinner=False)
def songs_from_notion():
    """Lee la base completa; no escribe en Notion."""
    source_id = api.find_source()
    return api.query_songs(source_id)


def read_children(block_id: str) -> list[dict]:
    blocks = []
    cursor = None
    while True:
        params = {'page_size': 100}
        if cursor:
            params['start_cursor'] = cursor
        data = api.request('GET', f'/blocks/{block_id}/children', params=params)
        blocks.extend(data.get('results', []))
        cursor = data.get('next_cursor')
        if not data.get('has_more') or not cursor:
            break
    return blocks


@st.cache_data(ttl=90, show_spinner=False)
def content_from_notion(page_id: str):
    """Descarga todo el texto (paginado) y los bloques interiores más comunes."""
    result = []

    def visit(parent_id: str, depth: int = 0):
        if depth > 5 or len(result) > 2500:
            return
        for block in read_children(parent_id):
            if block.get('type') in ('child_database', 'child_page'):
                continue
            result.append(block)
            if block.get('has_children') and block.get('type') in (
                'toggle', 'bulleted_list_item', 'numbered_list_item', 'quote', 'callout', 'column_list', 'column'
            ):
                visit(block['id'], depth + 1)

    visit(page_id)
    return music_from_blocks(result)


def get_select(page, name: str) -> str:
    prop = page.get('properties', {}).get(name, {})
    item = prop.get(prop.get('type', ''), None)
    if isinstance(item, dict):
        return item.get('name', '')
    return ''


def get_multiselect(page, name: str) -> list[str]:
    prop = page.get('properties', {}).get(name, {})
    return [x.get('name', '') for x in prop.get('multi_select', [])]


def is_published(page) -> bool:
    status = api.normalized(get_select(page, 'Estado'))
    return status in ('publico', 'publicado', 'published')


def root_key(page):
    note = get_select(page, 'Nota')
    structure = api.normalized(get_select(page, 'Estructura'))
    if not note:
        return None, ''
    try:
        root = PREFERRED[pitch_class(note)]
    except ValueError:
        return None, ''
    minor = structure == 'menor'
    return root, root + ('m' if minor else '')


st.markdown("""
<style>
.block-container {max-width:1250px; padding-top:2rem;}
.main-title {font-size:2.4rem; font-weight:750; margin-bottom:0px;}
.subhead {color:#a8abb6; margin-bottom:26px;}
[data-testid='stSidebar'] {background:#18191f;}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="main-title">🎶 Cancionero Caná</div><div class="subhead">Cantos, acordes y transposición en tiempo real</div>',
            unsafe_allow_html=True)

if not api.TOKEN:
    st.error('No se encontró NOTION_API_TOKEN. Conserva el archivo .env junto a app.py y conexion_notion.py.')
    st.stop()

try:
    with st.spinner('Conectando con Notion…'):
        songs = songs_from_notion()
except (SystemExit, ValueError, KeyError, OSError) as error:
    st.error('No se pudieron obtener las canciones de Notion. Comprueba los permisos y el archivo .env.')
    st.caption(str(error))
    st.stop()

songs = [song for song in songs if is_published(song)]
songs.sort(key=lambda x: api.normalized(api.song_title(x)))

with st.sidebar:
    st.header('Buscar canciones')
    search = st.text_input('Título', placeholder='Busca un canto...')
    categories = sorted({c for song in songs for c in get_multiselect(song, 'Categoria') or get_multiselect(song, 'Categoría')})
    category = st.selectbox('Categoría', ['Todas'] + categories)
    st.divider()
    font_size = st.slider('Tamaño de la letra', 14, 28, 18)
    show_chords = st.toggle('Mostrar acordes', value=True)
    prevent_overlap = st.toggle('Evitar que se encimen los acordes', value=True, help='Si dos acordes transportados chocan, los coloca en distintas líneas sin cambiar la letra.')
    notation = st.selectbox('Enarmonía', ['Automática', 'Sostenidos (#)', 'Bemoles (b)'])
    notation_code = {'Automática': 'auto', 'Sostenidos (#)': 'sostenidos', 'Bemoles (b)': 'bemoles'}[notation]
    st.divider()
    if st.button('🔄 Actualizar canciones', use_container_width=True):
        songs_from_notion.clear()
        content_from_notion.clear()
        st.rerun()
    st.caption('Caná v0.3.2 · Solo lectura de Notion · Se muestran los cantos con Estado = Publico.')

filtered = [song for song in songs if (not search or api.normalized(search) in api.normalized(api.song_title(song)))
            and (category == 'Todas' or category in (get_multiselect(song, 'Categoria') or get_multiselect(song, 'Categoría')))]

if not filtered:
    st.info('No hay canciones para este filtro. Comprueba el campo Estado o cambia la búsqueda.')
    st.stop()

left, right = st.columns([1, 2.6], gap='large')
with left:
    st.subheader(f'Canciones ({len(filtered)})')
    ids = [song['id'] for song in filtered]
    if 'selected_song' not in st.session_state or st.session_state.selected_song not in ids:
        st.session_state.selected_song = ids[0]
    for song in filtered:
        if st.button('♫ ' + api.song_title(song), key='song_' + song['id'],
                     use_container_width=True, type='primary' if song['id'] == st.session_state.selected_song else 'secondary'):
            st.session_state.selected_song = song['id']
            st.rerun()

current = next(song for song in filtered if song['id'] == st.session_state.selected_song)
title = api.song_title(current)
base_root, original_key = root_key(current)
step_key = 'transposition_' + current['id']
if step_key not in st.session_state:
    st.session_state[step_key] = 0

with right:
    st.subheader(title)
    cols = st.columns([1.5, 1, 1])
    with cols[0]:
        st.caption('Tonalidad original: ' + (original_key or 'Sin definir'))
    with cols[1]:
        st.caption('Estructura: ' + (get_select(current, 'Estructura') or '—'))
    with cols[2]:
        st.caption('Nota: ' + (get_select(current, 'Nota') or '—'))

    c1, c2, c3, c4 = st.columns([1.2, 1.5, 1.2, 1.7], vertical_alignment='center')
    with c1:
        if st.button('− 1 semitono', use_container_width=True):
            st.session_state[step_key] -= 1
    with c2:
        if base_root:
            index = (pitch_class(base_root) + st.session_state[step_key]) % 12
            shown = PREFERRED[index] + ('m' if api.normalized(get_select(current, 'Estructura')) == 'menor' else '')
            st.markdown(f'**Tono: {shown}**')
        else:
            st.markdown('**Tono: —**')
    with c3:
        if st.button('+ 1 semitono', use_container_width=True):
            st.session_state[step_key] += 1
    with c4:
        if st.button('↺ Tono original', use_container_width=True):
            st.session_state[step_key] = 0

    if not base_root:
        st.warning('Esta canción no tiene una nota original identificada en la base. Puedes cambiar sus acordes, pero revisa el campo Nota.')
    st.caption(f'Semitonos desde el original: {st.session_state[step_key]:+d}')

    try:
        with st.spinner('Cargando letra y acordes…'):
            music = content_from_notion(current['id'])
    except (SystemExit, ValueError, KeyError, OSError) as error:
        st.error('No pude leer el contenido de esta canción. Comprueba el acceso de Notion.')
        st.caption(str(error))
        st.stop()

    if not music:
        st.warning('La canción no contiene texto legible todavía.')
    else:
        st.markdown(CSS, unsafe_allow_html=True)
        st.markdown(render_song(music, st.session_state[step_key], show_chords, font_size, notation_code, prevent_overlap),
                    unsafe_allow_html=True)
        unresolved = [item['text'] for item in music if item.get('unparsed_yellow')]
        if unresolved:
            st.warning(f'{len(unresolved)} línea(s) con amarillo aún no se reconocieron como acordes. No se transponen por seguridad.')
            with st.expander('Diagnóstico de líneas amarillas no reconocidas'):
                st.caption('Si continúa el error, comparte únicamente este diagnóstico (no contiene tu token de Notion).')
                st.code('\n'.join(repr(text) for text in unresolved), language='text')
        st.caption('Vista de solo lectura. Caná v0.3.2 conserva las columnas de los acordes; si en Notion un acorde está sobre la sílaba equivocada, corrige únicamente esa canción y pulsa Actualizar canciones. Revisa el resultado musical antes de usarlo en vivo.')
