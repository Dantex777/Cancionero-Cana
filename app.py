"""Cancionero Caná v0.3.3: interfaz compacta para móvil."""
from pathlib import Path
import os
import sys

import streamlit as st
from dotenv import load_dotenv

from musica import CSS, music_from_blocks, render_song, pitch_class, PREFERRED

st.set_page_config(page_title='Cancionero Caná', page_icon='🎶', layout='wide',
                   initial_sidebar_state='collapsed')

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
/* Evita los márgenes de escritorio en las pantallas de móviles. */
.block-container {max-width:1050px; padding-top:1.25rem;}
.main-title {font-size:2.1rem; font-weight:750; margin:0;}
.subhead {color:#a8abb6; margin-bottom:1.1rem; font-size:.9rem;}
[data-testid='stSidebar'] {background:#18191f;}

/* Barra de tono: cuatro controles siempre en una sola fila,
   incluso cuando Streamlit apila las columnas en un móvil. */
.st-key-cana_toneline [data-testid='stHorizontalBlock'] {
    flex-wrap:nowrap !important;
    gap:.35rem !important;
    align-items:center !important;
}
.st-key-cana_toneline [data-testid='stColumn'] {
    min-width:0 !important;
    width:auto !important;
}
.st-key-cana_toneline [data-testid='stButton'] button {
    min-height:2.25rem;
    padding:.25rem .4rem;
    white-space:nowrap;
    font-size:.87rem;
}
.cana-tone-label {font-weight:750; font-size:1.04rem; white-space:nowrap;}

@media (max-width:640px) {
  .block-container {padding:0.75rem 0.7rem 3rem;}
  .main-title {font-size:1.55rem;}
  .subhead {font-size:.78rem; margin-bottom:.6rem;}
  .st-key-cana_toneline [data-testid='stHorizontalBlock'] {gap:.2rem !important;}
  .st-key-cana_toneline [data-testid='stButton'] button {
      font-size:.76rem; padding:.25rem .1rem;
  }
  .cana-tone-label {font-size:.87rem;}
}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="main-title">🎶 Cancionero Caná</div><div class="subhead">Letras y acordes con transposición</div>',
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
    st.header('Buscar y ajustar')
    search = st.text_input('Título', placeholder='Busca un canto...')
    categories = sorted({c for song in songs for c in get_multiselect(song, 'Categoria') or get_multiselect(song, 'Categoría')})
    category = st.selectbox('Categoría', ['Todas'] + categories)
    st.divider()
    font_size = st.slider('Tamaño de la letra', 12, 28, 14, key='cana_font_size')
    show_chords = st.toggle('Mostrar acordes', value=True)
    prevent_overlap = st.toggle('Evitar que se encimen los acordes', value=True, help='Si dos acordes transportados chocan, los coloca en distintas líneas sin cambiar la letra.')
    notation = st.selectbox('Enarmonía', ['Automática', 'Sostenidos (#)', 'Bemoles (b)'])
    notation_code = {'Automática': 'auto', 'Sostenidos (#)': 'sostenidos', 'Bemoles (b)': 'bemoles'}[notation]
    st.divider()
    if st.button('🔄 Actualizar canciones', use_container_width=True):
        songs_from_notion.clear()
        content_from_notion.clear()
        st.rerun()
    st.caption('Caná v0.3.3 · Solo lectura de Notion · Solo cantos con Estado = Público.')

filtered = [song for song in songs if (not search or api.normalized(search) in api.normalized(api.song_title(song)))
            and (category == 'Todas' or category in (get_multiselect(song, 'Categoria') or get_multiselect(song, 'Categoría')))]

if not filtered:
    st.info('No hay canciones para este filtro. Comprueba el campo Estado o cambia la búsqueda.')
    st.stop()

# Lista desplegable con búsqueda incorporada: la letra aparece justo debajo.
# No se muestran decenas de botones antes de la canción en pantallas pequeñas.
ids = [song['id'] for song in filtered]
by_id = {song['id']: song for song in filtered}
if st.session_state.get('selected_song') not in ids:
    st.session_state['selected_song'] = ids[0]

st.selectbox(
    '🎵 Buscar o seleccionar canción',
    options=ids,
    format_func=lambda song_id: api.song_title(by_id[song_id]),
    key='selected_song',
    help='Abre la lista o escribe parte del título para encontrar un canto.',
)
current = by_id[st.session_state['selected_song']]
title = api.song_title(current)
base_root, original_key = root_key(current)
step_key = 'transposition_' + current['id']
if step_key not in st.session_state:
    st.session_state[step_key] = 0

st.subheader(title)
metadata = [
    'Original: ' + (original_key or 'Sin definir'),
    'Estructura: ' + (get_select(current, 'Estructura') or '—'),
]
st.caption(' · '.join(metadata))

if base_root:
    index = (pitch_class(base_root) + st.session_state[step_key]) % 12
    current_key = PREFERRED[index] + ('m' if api.normalized(get_select(current, 'Estructura')) == 'menor' else '')
else:
    current_key = '—'

# Sin filas gigantes: se ve como «Tono: G  [−1] [+1] [↺ Original]».
with st.container(key='cana_toneline'):
    ctone, cdown, cup, coriginal = st.columns(
        [1.7, .9, .9, 1.8], gap='small', vertical_alignment='center'
    )
    with ctone:
        st.markdown(f'<div class="cana-tone-label">Tono: {current_key}</div>',
                    unsafe_allow_html=True)
    with cdown:
        if st.button('−1', key='minus_'+current['id'],
                     use_container_width=True, help='Bajar un semitono'):
            st.session_state[step_key] -= 1
            st.rerun()
    with cup:
        if st.button('+1', key='plus_'+current['id'],
                     use_container_width=True, help='Subir un semitono'):
            st.session_state[step_key] += 1
            st.rerun()
    with coriginal:
        if st.button('↺ Original', key='reset_'+current['id'],
                     use_container_width=True, help='Volver al tono original'):
            st.session_state[step_key] = 0
            st.rerun()

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
    st.caption('Vista de solo lectura. Caná v0.3.3 conserva las columnas de los acordes; si en Notion un acorde está sobre la sílaba equivocada, corrige únicamente esa canción y pulsa Actualizar canciones. Revisa el resultado musical antes de usarlo en vivo.')
