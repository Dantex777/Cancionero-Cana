"""Cancionero Caná v0.4.3 beta: Scroll integrado y versión visible."""
from pathlib import Path
import html
import os
import sys
import time

import streamlit as st
from dotenv import load_dotenv

from musica import CSS, music_from_blocks, render_song, pitch_class, PREFERRED, SHARPS, FLATS
from cana_interactions import render_autoscroll_song, sidebar_helper_html

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


def lyric_lines(music: list[dict]) -> list[str]:
    """Obtiene fragmentos legibles de letra, sin las líneas musicales de acordes."""
    lines = []
    for item in music:
        if item.get('type') == 'pair':
            raw = item.get('lyrics', '')
        elif item.get('type') in ('text', 'inline_annotation'):
            raw = item.get('text', '')
        else:
            continue
        for line in raw.splitlines():
            cleaned = line.strip()
            if cleaned:
                lines.append(cleaned)
    return lines


@st.cache_data(ttl=300, show_spinner=False)
def lyric_index(song_ids: tuple[str, ...]) -> tuple[dict[str, dict], int]:
    """Índice de letra + extractos para resultados; sólo se crea si buscan.

    Cada canción se obtiene de Notion una vez por periodo de caché. Se limitan
    las llamadas consecutivas para no sobrecargar el servicio.
    """
    index, failures = {}, 0
    for i, song_id in enumerate(song_ids):
        if i:
            time.sleep(0.37)
        try:
            lines = lyric_lines(content_from_notion(song_id))
            index[song_id] = {
                'text': api.normalized(' '.join(lines)),
                'lines': lines,
            }
        except (SystemExit, ValueError, KeyError, OSError):
            failures += 1
            index[song_id] = {'text': '', 'lines': []}
    return index, failures


def search_preview(song_info: dict, search_term: str, max_chars: int = 140) -> str:
    """Devuelve una línea de la canción que contiene la frase buscada."""
    lines = song_info.get('lines', [])
    if not lines:
        return 'Sin fragmento disponible para mostrar.'
    picked = next((line for line in lines if search_term in api.normalized(line)), None)
    if picked is None:
        # Coincidencia distribuida entre varias líneas, o sólo en el título.
        picked = ' '.join(lines[:2])
    picked = ' '.join(picked.split())
    if len(picked) > max_chars:
        picked = picked[:max_chars].rsplit(' ', 1)[0] + '…'
    return picked


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


def catalogue_candidates(pages: list[dict], category: str, query: str) -> list[dict]:
    """Filtra por título y categoría; conserva el orden alfabético recibido."""
    term = api.normalized(query.strip())
    return [page for page in pages if
            (category == 'Todas' or category in
             (get_multiselect(page, 'Categoria') or get_multiselect(page, 'Categoría'))) and
            (not term or term in api.normalized(api.song_title(page)))]


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
.st-key-cana_search_results [data-testid='stButton'] button {
    justify-content:flex-start !important; text-align:left !important;
    white-space:normal !important; height:auto; min-height:2.55rem;
    line-height:1.3; border:1px solid #404459;
    border-left:3px solid #b9adfa; background:#202331;
    color:#f4c58d;
}
.st-key-cana_search_results [data-testid='stButton'] button:hover {
    background:#2b3043; border-color:#baaafa;
}
.cana-result-preview {
    color:#b8bbca; font-size:.78rem; line-height:1.4;
    padding:.15rem .25rem .85rem .45rem; margin-bottom:.3rem;
    border-bottom:1px solid #343640;
}
/* Lista del catálogo: un renglón grande por canción para facilitar el uso táctil. */
.st-key-cana_catalogue [data-testid='stButton'] button {
    width:100%; justify-content:flex-start; text-align:left;
    border:1px solid #3b3c51; border-left:3px solid #b9adfa;
    background:#1d202a; color:#f4c58d;
    min-height:2.65rem; height:auto; white-space:normal;
    line-height:1.35; font-weight:650;
}
.st-key-cana_catalogue [data-testid='stButton'] button:hover {
    background:#292c3a; border-color:#b9adfa;
}
.cana-catalogue-meta {font-size:.83rem; color:#aeb4c9; margin:-.40rem 0 .65rem .32rem;}
.cana-catalogue-preview {font-size:.82rem; color:#dddde7; font-style:italic; margin:-.34rem 0 .85rem .32rem;}
.cana-catalogue-letter {font-size:1.12rem; font-weight:760; color:#b9adfa; margin:1.3rem 0 .6rem;}


/* La barra de tono se mantiene compacta en teléfonos. */
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
# En el catálogo dejamos espacio para explorar la lista sin desplazarla por la portada.
if not st.session_state.get('cana_catalog_view', False):
    if PORTADA.is_file():
        with st.container(key='cana_banner'):
            st.image(str(PORTADA), use_container_width=True)
    else:
        st.warning('No se encontró portada_cantoral_cana.webp en la misma carpeta de app.py.')
st.markdown('<div class="cana-brand-title"><span class="cana-brand-text">Cancionero Caná</span></div>',
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

# La navegación está completamente en el menú lateral para que, en el
# teléfono, la canción aparezca al principio y no debajo de una lista larga.
if not songs:
    st.info('Aún no hay canciones marcadas como Público en Notion.')
    st.stop()

if 'cana_active_song' not in st.session_state:
    st.session_state['cana_active_song'] = songs[0]['id']
if 'cana_picker_revision' not in st.session_state:
    st.session_state['cana_picker_revision'] = 0
if 'cana_search_query' not in st.session_state:
    st.session_state['cana_search_query'] = ''
if 'cana_catalog_view' not in st.session_state:
    st.session_state['cana_catalog_view'] = False
if 'cana_close_sidebar_token' not in st.session_state:
    st.session_state['cana_close_sidebar_token'] = 0


def show_catalogue():
    """Abre una lista opcional, sin modificar la canción elegida."""
    st.session_state['cana_catalog_view'] = True
    st.session_state['cana_close_sidebar_token'] += 1


def hide_catalogue():
    """Regresa a la canción que estaba abierta."""
    st.session_state['cana_catalog_view'] = False
    st.session_state['cana_close_sidebar_token'] += 1


def choose_song(song_id: str):
    """Cambia el canto desde resultados, y deja lista una nueva búsqueda."""
    st.session_state['cana_active_song'] = song_id
    st.session_state['cana_catalog_view'] = False
    st.session_state['cana_search_query'] = ''
    st.session_state['cana_picker_revision'] += 1
    st.session_state['cana_close_sidebar_token'] += 1


with st.sidebar:
    st.header('Canciones')

    # 1. Categoría
    categories = sorted({
        c for song in songs
        for c in (get_multiselect(song, 'Categoria') or get_multiselect(song, 'Categoría'))
    })
    category = st.selectbox('Categoría', ['Todas'] + categories, key='cana_category')
    candidates = [
        song for song in songs
        if category == 'Todas' or category in (
            get_multiselect(song, 'Categoria') or get_multiselect(song, 'Categoría')
        )
    ]
    by_id = {song['id']: song for song in candidates}
    ids = list(by_id)
    if st.session_state['cana_active_song'] not in by_id and ids:
        st.session_state['cana_active_song'] = ids[0]

    # 2. Selector de canciones, siempre disponible y con búsqueda por título.
    picker_key = f'cana_picker_{st.session_state["cana_picker_revision"]}'

    def select_a_song():
        selected = st.session_state.get(picker_key)
        if selected:
            choose_song(selected)

    st.selectbox(
        'Seleccionar canción',
        options=ids,
        index=None,
        placeholder='Elige una canción…',
        format_func=lambda song_id: api.song_title(by_id[song_id]),
        key=picker_key,
        on_change=select_a_song,
        help='Escribe parte del título. Al elegir un canto, el selector vuelve a quedar vacío.',
    )

    # 3. Búsqueda por nombre O frase de la letra, con resultados clicables.
    search_query = st.text_input(
        'Buscar por letra o nombre',
        key='cana_search_query',
        placeholder='Ej.: a la roca de mi salvación',
        help='Aparecerán las canciones coincidentes y una pequeña vista previa de su letra.',
    ).strip()
    folded_query = api.normalized(search_query)
    if folded_query:
        index = {}
        failures = 0
        if len(folded_query) >= 3:
            with st.spinner('Buscando en las letras…'):
                index, failures = lyric_index(tuple(song['id'] for song in songs))

        matches = [song for song in candidates if
                   folded_query in api.normalized(api.song_title(song)) or
                   (len(folded_query) >= 3 and
                    folded_query in index.get(song['id'], {}).get('text', ''))]
        st.caption(f'{len(matches)} canción(es) encontrada(s)')
        if failures:
            st.caption(f'No fue posible revisar el texto de {failures} canto(s).')
        if not matches:
            st.info('No hay coincidencias. Prueba con otra frase o categoría.')
        else:
            with st.container(key='cana_search_results'):
                for song in matches[:12]:
                    song_id = song['id']
                    song_title = api.song_title(song)
                    st.button(
                        song_title,
                        key=f'cana_search_result_{song_id}',
                        use_container_width=True,
                        on_click=choose_song,
                        args=(song_id,),
                        help='Abrir esta canción',
                    )
                    song_index = index.get(song_id, {})
                    preview = search_preview(song_index, folded_query) if song_index else ''
                    if preview:
                        st.markdown(
                            f'<div class="cana-result-preview">{html.escape(preview)}</div>',
                            unsafe_allow_html=True,
                        )
                if len(matches) > 12:
                    st.caption(f'Se muestran 12 de {len(matches)}; afina la búsqueda para ver las demás.')

    # 4. Acceso opcional a la lista completa, justo debajo de los buscadores.
    if st.session_state['cana_catalog_view']:
        st.button('← Volver a la canción', key='cana_catalog_back_sidebar',
                  use_container_width=True, on_click=hide_catalogue)
        st.caption('Estás viendo la biblioteca completa de cantos.')
    else:
        st.button('📚 Ver catálogo completo', key='cana_catalog_open_sidebar',
                  use_container_width=True, on_click=show_catalogue)

    st.divider()
    # Las preferencias quedan después del buscador, como solicitó el usuario.
    st.subheader('Visualización')
    font_size = st.slider('Tamaño de la letra', 12, 28, 14, key='cana_font_size')
    font_style = st.selectbox(
        'Tipo de letra de las canciones',
        ['Mono (alineación original)', 'Comic Sans', 'Futura', 'Helvetica'],
        key='cana_song_font',
        help='Mono conserva exactamente el espaciado definido en Notion.',
    )
    font_code = {
        'Mono (alineación original)': 'mono',
        'Comic Sans': 'comic', 'Futura': 'futura', 'Helvetica': 'helvetica',
    }[font_style]
    show_chords = st.toggle('Mostrar acordes', value=True)
    prevent_overlap = st.toggle(
        'Separar acordes amontonados (plan B)',
        value=False,
        key='cana_overlap_fallback_v038',
        help='Actívalo solo si los acordes se amontonan. Algunos acordes pueden pasar a otra línea.',
    )
    st.caption('Activar solo como plan B ante acordes amontonados; puede mover acordes a otra línea.')
    notation = st.selectbox(
        'Enarmonía', ['Sostenidos (#)', 'Bemoles (b)', 'Automática'],
        key='cana_notation'
    )
    notation_code = {
        'Automática': 'auto', 'Sostenidos (#)': 'sostenidos',
        'Bemoles (b)': 'bemoles',
    }[notation]
    st.divider()
    if st.button('🔄 Actualizar canciones', use_container_width=True):
        songs_from_notion.clear()
        content_from_notion.clear()
        lyric_index.clear()
        st.rerun()

# Mantener el control del menú en la zona principal evita que se desmonte
# cuando el usuario contrae la barra lateral en un teléfono.
st.html(sidebar_helper_html(st.session_state['cana_close_sidebar_token']), unsafe_allow_javascript=True)

# Vista alternativa opcional: biblioteca de títulos, sin cambiar de aplicación.
# No consultamos las letras por defecto: Notion sólo se carga si el usuario
# decide mostrar fragmentos. Esto evita llamadas innecesarias durante una misa.
if st.session_state['cana_catalog_view']:
    st.markdown('<div class="cana-song-title">Biblioteca de canciones</div>',
                unsafe_allow_html=True)
    st.caption('Explora todos los cantos publicados. Pulsa un título para abrir la canción y su transpositor.')
    st.button('← Regresar al visor musical', on_click=hide_catalogue,
              key='cana_catalog_back_main')

    catalogue_query = st.text_input(
        'Filtrar catálogo por título', placeholder='Escribe parte del nombre...',
        key='cana_catalog_filter',
    )
    catalogue_songs = catalogue_candidates(songs, category, catalogue_query)
    st.caption(f'{len(catalogue_songs)} de {len(candidates)} canciones en la categoría «{category}».')

    if not catalogue_songs:
        st.info('No hay cantos con ese título en esta categoría.')
    else:
        # En repertorios grandes la paginación evita una página excesiva.
        page_size = 40
        pages = (len(catalogue_songs) + page_size - 1) // page_size
        page = (st.selectbox('Página del catálogo', range(1, pages + 1),
                             key='cana_catalog_page') if pages > 1 else 1)
        visible = catalogue_songs[(page-1)*page_size:page*page_size]
        show_previews = st.toggle(
            'Mostrar un fragmento de cada canción (opcional)', value=False,
            key='cana_catalog_previews',
            help='Carga las letras de esta página desde Notion. Desactívalo para una lista más rápida.',
        )
        previews, failures = ({}, 0)
        if show_previews:
            with st.spinner('Cargando pequeños fragmentos de letra desde Notion…'):
                previews, failures = lyric_index(tuple(song['id'] for song in visible))
        if failures:
            st.caption(f'No fue posible obtener fragmentos de {failures} canciones.')

        previous_letter = None
        with st.container(key='cana_catalogue'):
            for song in visible:
                song_id = song['id']
                title = api.song_title(song)
                letter = api.normalized(title)[:1].upper() or '#'
                if letter != previous_letter:
                    st.markdown(f'<div class="cana-catalogue-letter">{html.escape(letter)}</div>',
                                unsafe_allow_html=True)
                    previous_letter = letter
                st.button(title, key=f'cana_catalog_song_{song_id}',
                          on_click=choose_song, args=(song_id,),
                          use_container_width=True,
                          help='Abrir canto con acordes y transposición')
                _root, song_key = root_key(song)
                tags = (get_multiselect(song, 'Categoria') or
                        get_multiselect(song, 'Categoría'))
                details = [song_key or 'Tono sin definir'] + tags
                st.markdown('<div class="cana-catalogue-meta">' +
                            html.escape(' · '.join(details)) + '</div>',
                            unsafe_allow_html=True)
                if show_previews:
                    entry = previews.get(song_id, {})
                    excerpt = search_preview(entry, '', max_chars=135)
                    st.markdown('<div class="cana-catalogue-preview">' +
                                html.escape(excerpt) + '</div>', unsafe_allow_html=True)
    st.caption('Versión de pruebas: v0.4.3 beta · Auto Scroll integrado')
    st.stop()

# Vista musical normal: sin listas que empujen el canto hacia abajo.
if not ids:
    st.info('Esta categoría todavía no tiene canciones públicas.')
    st.stop()
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
    st.html(render_autoscroll_song(render_song(music, st.session_state[step_key], show_chords, font_size, notation_code, prevent_overlap, font_code)), unsafe_allow_javascript=True)
    unresolved = [item['text'] for item in music if item.get('unparsed_yellow')]
    if unresolved:
        st.warning(f'{len(unresolved)} línea(s) con amarillo aún no se reconocieron como acordes. No se transponen por seguridad.')
        with st.expander('Diagnóstico de líneas amarillas no reconocidas'):
            st.caption('Si continúa el error, comparte únicamente este diagnóstico (no contiene tu token de Notion).')
            st.code('\n'.join(repr(text) for text in unresolved), language='text')



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


st.caption('Versión de pruebas: v0.4.3 beta · Auto Scroll integrado · rama feature/autoscroll-menu-v041')
