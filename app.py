"""Cancionero Caná v0.3.6: portada y paleta visual, con la búsqueda y transposición intactas."""
from pathlib import Path
import html
import os
import sys
import time

import streamlit as st
from dotenv import load_dotenv

from musica import CSS, music_from_blocks, render_song, pitch_class, PREFERRED, SHARPS, FLATS

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


@st.cache_data(ttl=300, show_spinner=False)
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


@st.cache_data(ttl=300, show_spinner=False)
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



def searchable_lyrics(music: list[dict]) -> str:
    """Extrae sólo letra y anotaciones, sin líneas de acordes amarillos."""
    pieces = []
    for item in music:
        if item.get('type') == 'pair':
            pieces.append(item.get('lyrics', ''))
        elif item.get('type') in ('text', 'inline_annotation'):
            pieces.append(item.get('text', ''))
    return api.normalized(' '.join(pieces))


@st.cache_data(ttl=300, show_spinner=False)
def lyric_index(song_ids: tuple[str, ...]) -> tuple[dict[str, str], int]:
    """Índice en caché para búsquedas por frases, construido bajo demanda.

    Al buscar por letra la primera vez se leen las canciones publicadas desde
    Notion. Los resultados se comparten en caché entre visitas durante 5 min.
    Se espacian las llamadas para respetar el límite habitual de la API.
    """
    index, failures = {}, 0
    for i, song_id in enumerate(song_ids):
        if i:
            time.sleep(0.37)
        try:
            index[song_id] = searchable_lyrics(content_from_notion(song_id))
        except (SystemExit, ValueError, KeyError, OSError):
            failures += 1
            index[song_id] = ''
    return index, failures



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

/* Identidad visual del Cantoral Caná (colores accesibles sobre modo oscuro). */
.st-key-cana_banner {margin-bottom:.30rem;}
.st-key-cana_banner [data-testid="stImage"] img {
    width:100%; max-height:310px; object-fit:cover; object-position:center 52%;
    border-radius:15px; border:1px solid #393852;
    box-shadow:0 11px 32px rgba(6,7,21,.24);
}
.cana-brand-title {
    display:flex; align-items:center; gap:.55rem; flex-wrap:wrap;
    font-size:2.10rem; line-height:1.25; font-weight:800; margin: .45rem 0 .10rem;
}
.cana-brand-text {
    background:linear-gradient(110deg,#c7aaff 10%,#8bc7f7 78%);
    -webkit-background-clip:text; background-clip:text;
    -webkit-text-fill-color:transparent;
}
.cana-brand-icon {
    display:inline-block;
    font-family:'Segoe UI Symbol','Apple Symbols',sans-serif;
    font-size:1.05em;
    color:#f5f5f7 !important;
    -webkit-text-fill-color:#f5f5f7 !important;
    -webkit-text-stroke:1.15px #08090e;
    text-shadow:0 0 1px #05060a, 1px 1px 0 #05060a, -1px -1px 0 #05060a;
    filter:grayscale(1);
}
.cana-song-title {
    color:#f4c58d !important; -webkit-text-fill-color:#f4c58d !important;
    font-size:1.75rem; font-weight:800;
    line-height:1.2; margin:1rem 0 .45rem;
}

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
  .st-key-cana_banner [data-testid="stImage"] img {
      max-height:none; height:auto; object-fit:contain; border-radius:10px;
  }
  .cana-brand-title {font-size:1.55rem; margin:.30rem 0 .1rem;}
  .cana-song-title {font-size:1.30rem; margin:.8rem 0 .4rem;}
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
# Esta imagen se guarda junto a app.py en GitHub; no depende de Notion ni de URLs temporales.
PORTADA = Path(__file__).with_name('portada_cantoral_cana.webp')
if PORTADA.is_file():
    with st.container(key='cana_banner'):
        st.image(str(PORTADA), use_container_width=True)
else:
    st.warning('No se encontró portada_cantoral_cana.webp en la misma carpeta de app.py.')
st.markdown('<div class="cana-brand-title"><span class="cana-brand-icon">🎶︎</span><span class="cana-brand-text">Cancionero Caná</span></div><div class="subhead">Letras y acordes con transposición</div>',
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
    categories = sorted({c for song in songs for c in get_multiselect(song, 'Categoria') or get_multiselect(song, 'Categoría')})
    category = st.selectbox('Categoría', ['Todas'] + categories)
    st.divider()
    font_size = st.slider('Tamaño de la letra', 12, 28, 14, key='cana_font_size')
    font_style = st.selectbox(
        'Tipo de letra de las canciones',
        ['Mono (alineación original)', 'Comic Sans', 'Futura', 'Helvetica'],
        key='cana_song_font',
        help='Mono mantiene exactamente las columnas de Notion. Las otras fuentes colocan los acordes sobre las posiciones de las letras; comprueba las canciones antes de una celebración.',
    )
    font_code = {'Mono (alineación original)':'mono', 'Comic Sans':'comic', 'Futura':'futura', 'Helvetica':'helvetica'}[font_style]
    show_chords = st.toggle('Mostrar acordes', value=True)
    prevent_overlap = st.toggle('Evitar que se encimen los acordes', value=True, help='Si dos acordes transportados chocan, los coloca en distintas líneas sin cambiar la letra.')
    notation = st.selectbox('Enarmonía', ['Sostenidos (#)', 'Bemoles (b)', 'Automática'], key='cana_notation')
    notation_code = {'Automática': 'auto', 'Sostenidos (#)': 'sostenidos', 'Bemoles (b)': 'bemoles'}[notation]
    st.divider()
    if st.button('🔄 Actualizar canciones', use_container_width=True):
        songs_from_notion.clear()
        content_from_notion.clear()
        lyric_index.clear()
        st.rerun()
    st.caption('Caná v0.3.6 · Solo lectura de Notion · Cantos con Estado = Público.')

# Filtro global visible en móviles, incluso con el menú lateral cerrado.
# El desplegable de Streamlit busca sólo entre las etiquetas (títulos), por
# eso añadimos este campo para encontrar frases dentro del texto de los cantos.
if 'cana_search_query' not in st.session_state:
    st.session_state['cana_search_query'] = ''
query = st.text_input(
    '🔎 Buscar por título o letra',
    key='cana_search_query',
    placeholder='Ej.: a la roca de mi salvación',
    help='Escribe una parte del nombre o una frase de la letra y selecciona el canto.',
).strip()
normalized_query = api.normalized(query)

candidates = [song for song in songs if
              category == 'Todas' or category in (get_multiselect(song, 'Categoria') or get_multiselect(song, 'Categoría'))]

# No hacemos peticiones adicionales a Notion al abrir el cancionero.
# Las letras se indexan sólo cuando alguien efectivamente hace una búsqueda.
lyrics = {}
if len(normalized_query) >= 3:
    with st.spinner('Buscando en las letras de los cantos…'):
        lyrics, failures = lyric_index(tuple(song['id'] for song in songs))
    if failures:
        st.caption(f'No se pudieron indexar {failures} canción(es). Si falta algún resultado, pulsa Actualizar canciones.')

filtered = [song for song in candidates
            if not normalized_query
            or normalized_query in api.normalized(api.song_title(song))
            or (len(normalized_query) >= 3 and normalized_query in lyrics.get(song['id'], ''))]

if not filtered:
    st.info('No encontré canciones con esa frase. Prueba con otras palabras o cambia la categoría.')
    st.stop()

# Separamos la canción mostrada de la búsqueda dentro del selectbox. Cuando
# el usuario escoge una opción, el selector se monta otra vez vacío, listo para
# buscar un nuevo canto, sin borrar el título de la canción actualmente abierta.
ids = [song['id'] for song in filtered]
by_id = {song['id']: song for song in filtered}
if 'cana_active_song' not in st.session_state:
    st.session_state['cana_active_song'] = ids[0]
if st.session_state['cana_active_song'] not in ids:
    st.session_state['cana_active_song'] = ids[0]
if 'cana_picker_revision' not in st.session_state:
    st.session_state['cana_picker_revision'] = 0
picker_key = f'cana_picker_{st.session_state["cana_picker_revision"]}'


def select_a_song():
    selected = st.session_state.get(picker_key)
    if selected:
        st.session_state['cana_active_song'] = selected
        st.session_state['cana_picker_revision'] += 1
        st.session_state['cana_search_query'] = ''


st.selectbox(
    '🎵 Seleccionar canción',
    options=ids,
    index=None,
    placeholder='Toca para elegir o buscar otra canción…',
    format_func=lambda song_id: api.song_title(by_id[song_id]),
    key=picker_key,
    on_change=select_a_song,
    help='Puedes escribir parte del título en esta lista. Al elegir una canción, el buscador se limpia para la siguiente.',
)
current = by_id[st.session_state['cana_active_song']]
title = api.song_title(current)
base_root, original_key = root_key(current)
step_key = 'transposition_' + current['id']
if step_key not in st.session_state:
    st.session_state[step_key] = 0

st.markdown(f'<div class="cana-song-title" style="color:#f4c58d !important; -webkit-text-fill-color:#f4c58d !important;">{html.escape(title)}</div>', unsafe_allow_html=True)
metadata = [
    'Original: ' + (original_key or 'Sin definir'),
    'Estructura: ' + (get_select(current, 'Estructura') or '—'),
]
st.caption(' · '.join(metadata))

if base_root:
    index = (pitch_class(base_root) + st.session_state[step_key]) % 12
    tone_names = {'sostenidos': SHARPS, 'bemoles': FLATS, 'auto': PREFERRED}[notation_code]
    current_key = tone_names[index] + ('m' if api.normalized(get_select(current, 'Estructura')) == 'menor' else '')
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
    st.markdown(render_song(music, st.session_state[step_key], show_chords, font_size, notation_code, prevent_overlap, font_code),
                unsafe_allow_html=True)
    unresolved = [item['text'] for item in music if item.get('unparsed_yellow')]
    if unresolved:
        st.warning(f'{len(unresolved)} línea(s) con amarillo aún no se reconocieron como acordes. No se transponen por seguridad.')
        with st.expander('Diagnóstico de líneas amarillas no reconocidas'):
            st.caption('Si continúa el error, comparte únicamente este diagnóstico (no contiene tu token de Notion).')
            st.code('\n'.join(repr(text) for text in unresolved), language='text')
    st.caption('Vista de solo lectura. Caná v0.3.6 conserva las columnas de los acordes; si en Notion un acorde está sobre la sílaba equivocada, corrige únicamente esa canción y pulsa Actualizar canciones. Revisa el resultado musical antes de usarlo en vivo.')


# El pie aparece después de los cantos, sin modificar la estructura musical.
st.markdown("""
<style>
.cana-footer {border-top:1px solid #393945; margin:2.0rem 0 0; padding:1.35rem .15rem 2rem; font-size:.90rem;}
.cana-footer-note {color:#c9a7f5; font-style:italic; line-height:1.6; margin-bottom:.80rem;}
.cana-footer-help {color:#eceaf1; line-height:1.6;}
.cana-footer a, .cana-footer a:visited {color:#d3c0fb; text-decoration:underline; text-underline-offset:2px;}
</style>
<div class="cana-footer">
  <div class="cana-footer-note">Cantoral en construcción XD (Si llegaste hasta aquí, ten paciencia, pronto completaremos el cancionero 😉)</div>
  <div class="cana-footer-help">Si quieres ayudar o ser parte de completar este cancionero, escríbeme a <a href="mailto:davidfg77777@gmail.com">davidfg77777@gmail.com</a></div>
</div>
""", unsafe_allow_html=True)
