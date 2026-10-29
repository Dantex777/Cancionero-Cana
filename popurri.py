"""Cancionero Caná v0.5.0 beta — Popurrís (solo estado local, sin escrituras a Notion).

El motor musical y el Auto Scroll se reutilizan sin modificarlos.
La persistencia compartida en Notion se activará cuando exista otra base con
permisos apropiados y control de acceso para guardar repertorios.
"""
import html
import json
import uuid

from musica import CSS, FLATS, PREFERRED, SHARPS, pitch_class, render_song
from cana_interactions import render_autoscroll_song

MAX_SONGS = 30
KEYS = SHARPS + [note + "m" for note in SHARPS]


def semitone_difference(original: str, target: str) -> int:
    """Devuelve el desplazamiento cromático mínimo (hasta 6 semitonos)."""
    diff = (pitch_class(target.removesuffix("m")) - pitch_class(original)) % 12
    return diff - 12 if diff > 6 else diff


def effective_steps(item: dict, page: dict, mode: str, common: str, root_key) -> int:
    root, original = root_key(page)
    if mode == "Originales":
        return 0
    if mode == "Unificar tono" and root:
        if original.endswith("m") == common.endswith("m"):
            return semitone_difference(root, common)
        return 0  # No convierte automáticamente una canción mayor en menor.
    return int(item.get("steps", 0))


def target_name(page: dict, steps: int, root_key, notation: str) -> str:
    root, original = root_key(page)
    if not root:
        return "Sin nota original"
    names = {"sostenidos": SHARPS, "bemoles": FLATS, "auto": PREFERRED}[notation]
    label = names[(pitch_class(root) + steps) % 12]
    return label + ("m" if original.endswith("m") else "")


def show_popurri(st, songs, api, root_key, content_from_notion,
                 show_chords, font_size, notation_code, prevent_overlap, font_code):
    """Presenta constructor, transposición individual y visor concatenado."""
    song_by_id = {s["id"]: s for s in songs}
    state = st.session_state
    state.setdefault("cana_pop_items", [])
    state.setdefault("cana_pop_mode", "Originales")
    state.setdefault("cana_pop_target", "Bm")
    state.setdefault("cana_pop_title", "Popurrí de alabanzas")
    state.setdefault("cana_pop_revision", 0)

    # Nunca mantengas referencias a cantos borrados de Notion.
    state["cana_pop_items"] = [
        s for s in state["cana_pop_items"] if s.get("song_id") in song_by_id
    ]

    def add_song():
        song_id = state.get("cana_pop_new_song")
        if song_id in song_by_id and len(state["cana_pop_items"]) < MAX_SONGS:
            state["cana_pop_items"].append({
                "song_id": song_id, "steps": 0, "uid": uuid.uuid4().hex
            })
            state["cana_pop_revision"] += 1

    def move(uid: str, direction: int):
        items = state["cana_pop_items"]
        i = next((n for n, x in enumerate(items) if x["uid"] == uid), -1)
        j = i + direction
        if 0 <= i < len(items) and 0 <= j < len(items):
            items[i], items[j] = items[j], items[i]

    def remove(uid: str):
        state["cana_pop_items"] = [
            x for x in state["cana_pop_items"] if x["uid"] != uid
        ]

    def manual_shift(uid: str, change: int):
        items = state["cana_pop_items"]
        mode = state["cana_pop_mode"]
        target = state["cana_pop_target"]
        # Conservamos exactamente el tono que actualmente muestra cada canto.
        for item in items:
            item["steps"] = effective_steps(
                item, song_by_id[item["song_id"]], mode, target, root_key
            )
        state["cana_pop_mode"] = "Personalizado"
        for item in items:
            if item["uid"] == uid:
                item["steps"] += change
                break

    st.markdown('<div class="cana-song-title">Modo Popurrí · v0.5.0 beta</div>',
                unsafe_allow_html=True)
    st.caption("Crea un repertorio continuo. Los cambios aquí no modifican Notion ni las canciones originales.")

    st.text_input("Nombre del popurrí", key="cana_pop_title", max_chars=100)
    picker = st.selectbox(
        "Añadir canción", options=list(song_by_id),
        format_func=lambda song_id: api.song_title(song_by_id[song_id]),
        index=None, placeholder="Busca por título…", key="cana_pop_new_song",
    )
    st.button("＋ Añadir canto", on_click=add_song,
              disabled=not picker or len(state["cana_pop_items"]) >= MAX_SONGS)
    if not state["cana_pop_items"]:
        st.info("Elige un canto o carga un popurrí guardado en Notion.")

    # Streamlit ejecuta los callbacks antes de reconstruir los widgets.
    st.radio(
        "Tonalidades", ["Originales", "Unificar tono", "Personalizado"],
        key="cana_pop_mode", horizontal=True,
        help="Si modificas un canto con −1/+1, pasa automáticamente a Personalizado."
    )
    mode = state["cana_pop_mode"]
    target = st.selectbox(
        "Tonalidad común", KEYS, key="cana_pop_target",
        disabled=mode != "Unificar tono",
    )
    if mode == "Unificar tono":
        incompatible = [
            song_by_id[s["song_id"]]
            for s in state["cana_pop_items"]
            if (root_key(song_by_id[s["song_id"]])[1].endswith("m")
                != target.endswith("m"))
        ]
        if incompatible:
            st.warning(
                f"{len(incompatible)} canto(s) con modo mayor/menor distinto se "
                "mantienen en su tonalidad original. Revisa su armonía manualmente."
            )

    st.caption(f"{len(state['cana_pop_items'])} canciones · Orden de interpretación")
    st.markdown("""
    <style>
    .cana-pop-item {padding:.3rem 0 .15rem;color:#f4c58d;font-weight:750}
    .cana-pop-key {font-size:.8rem;color:#b6b4c7}
    .cana-popurri-body {padding:8px 15px 24px!important}
    .cana-popurri-body > .cana-song {
        overflow:visible!important;background:transparent!important;
        border:0!important;box-shadow:none!important;
        padding:8px 2px 18px!important;margin:0!important;
    }
    .cana-pop-header{font-weight:800;font-size:1.15em;color:#f4c58d;
        padding:20px 2px 4px;border-top:1px solid #716f94}
    .cana-pop-subtitle{color:#b4b1c4;font-size:.78em;margin-bottom:10px}
    </style>
    """, unsafe_allow_html=True)

    for position, item in enumerate(state["cana_pop_items"]):
        song = song_by_id[item["song_id"]]
        steps = effective_steps(item, song, mode, target, root_key)
        _root, original = root_key(song)
        now = target_name(song, steps, root_key, notation_code)
        name = api.song_title(song)
        st.markdown(
            f'<div class="cana-pop-item">{position+1}. {html.escape(name)}</div>'
            f'<div class="cana-pop-key">Original: {html.escape(original or "—")} '
            f'· Actual: {html.escape(now)} · {steps:+d} semitonos</div>',
            unsafe_allow_html=True
        )
        a,b,c,d,e = st.columns([1,1,1,1,1])
        with a:
            st.button("−1", key="pop_down_"+item["uid"],
                      on_click=manual_shift,args=(item["uid"], -1),
                      use_container_width=True)
        with b:
            st.button("+1", key="pop_up_"+item["uid"],
                      on_click=manual_shift,args=(item["uid"], 1),
                      use_container_width=True)
        with c:
            st.button("↑", key="pop_move_up_"+item["uid"],disabled=position==0,
                      on_click=move,args=(item["uid"], -1),
                      use_container_width=True)
        with d:
            st.button("↓", key="pop_move_down_"+item["uid"],
                      disabled=position==len(state["cana_pop_items"])-1,
                      on_click=move,args=(item["uid"], 1),
                      use_container_width=True)
        with e:
            st.button("✕", key="pop_remove_"+item["uid"],
                      on_click=remove,args=(item["uid"],),
                      use_container_width=True)

    # Compartir manualmente con archivo mientras configuramos la base de Notion.
    # No escribir desde una app pública con el token de lectura actual.
    saved = {
        "format": "cana-popurri-v1",
        "name": state["cana_pop_title"],
        "mode": mode,
        "target": target,
        "songs": [
            {"song_id":i["song_id"],
             "steps":effective_steps(i, song_by_id[i["song_id"]],mode,target,root_key)}
            for i in state["cana_pop_items"]
        ],
    }
    st.download_button(
        "Guardar copia del popurrí (.json)",
        json.dumps(saved, ensure_ascii=False, indent=2),
        file_name="popurri-cana.json", mime="application/json",
        help="Copia local para compartir o recuperar el popurrí.",
        disabled=not state["cana_pop_items"]
    )

    def import_saved():
        # Callback: se ejecuta antes de crear text_input y radio, por lo que
        # podemos restaurar sus estados sin StreamlitAPIException.
        uploaded = state.get("cana_pop_import")
        if uploaded is None:
            return
        try:
            data = json.loads(uploaded.getvalue().decode("utf-8"))
            if not isinstance(data, dict) or data.get("format") != "cana-popurri-v1":
                raise ValueError("Formato desconocido")
            selections = data.get("songs", [])
            if not isinstance(selections, list) or len(selections) > MAX_SONGS:
                raise ValueError("Cantidad de cantos inválida")
            valid = []
            for song in selections:
                if not isinstance(song, dict):
                    continue
                if song.get("song_id") in song_by_id:
                    valid.append({
                        "song_id": song["song_id"],
                        "steps": max(-24, min(24, int(song.get("steps", 0)))),
                        "uid": uuid.uuid4().hex,
                    })
            state["cana_pop_items"] = valid
            state["cana_pop_mode"] = "Personalizado"
            state["cana_pop_title"] = str(data.get("name", "Popurrí"))[:100]
            state["cana_pop_import_error"] = ""
        except (ValueError, TypeError, UnicodeError, KeyError, AttributeError):
            state["cana_pop_import_error"] = "No pude leer el archivo. Usa uno exportado desde Caná."

    with st.expander("Cargar popurrí desde archivo"):
        uploaded = st.file_uploader(
            "Archivo .json de Caná", type=["json"], key="cana_pop_import")
        st.button("Importar repertorio", on_click=import_saved,
                  disabled=uploaded is None)
        if state.get("cana_pop_import_error"):
            st.error(state["cana_pop_import_error"])

    # Guardado compartido en base separada; nunca se escribe en Canciones Caná.
    from popurri_notion import (
        configured as notion_ready, setting as notion_setting,
        list_saved as notion_list, create_saved as notion_save,
        PopurriNotionError,
    )
    import hmac

    with st.expander("Popurrís guardados en Notion"):
        st.caption("Los músicos pueden cargar repertorios; guardar nuevos "
                   "requiere clave de administración y permisos en una base aparte.")
        if not notion_ready(st):
            st.info("Para activar este guardado, crea la base «Popurrís Caná» "
                    "y configura su conexión en Streamlit Secrets.")
        else:
            if st.button("Actualizar lista de popurrís", key="cana_pop_refresh_notion"):
                try:
                    state["cana_pop_notion_rows"] = notion_list(st, set(song_by_id))
                    state["cana_pop_notion_error"] = ""
                except PopurriNotionError as err:
                    state["cana_pop_notion_error"] = str(err)

            if state.get("cana_pop_notion_error"):
                st.error(state["cana_pop_notion_error"])

            rows = state.get("cana_pop_notion_rows", [])
            by_saved_id = {row["id"]: row for row in rows}
            selected = st.selectbox(
                "Repertorio guardado", list(by_saved_id), index=None,
                format_func=lambda item_id: by_saved_id[item_id]["name"],
                placeholder="Selecciona un popurrí guardado…",
                key="cana_pop_selected_notion",
            )

            def load_notion_popurri():
                saved_id = state.get("cana_pop_selected_notion")
                if saved_id not in by_saved_id:
                    return
                data = by_saved_id[saved_id]["data"]
                state["cana_pop_items"] = [
                    {"song_id": row["song_id"], "steps": int(row["steps"]),
                     "uid": uuid.uuid4().hex}
                    for row in data["songs"]
                ]
                state["cana_pop_mode"] = "Personalizado"
                state["cana_pop_title"] = data["name"]
                state["cana_pop_target"] = (
                    data["target"] if data["target"] in KEYS else "Bm")

            st.button("Abrir repertorio", on_click=load_notion_popurri,
                      disabled=not selected)

            admin_secret = notion_setting(st, "POPURRIS_ADMIN_PASSWORD")
            if admin_secret:
                password = st.text_input("Clave para guardar (administración)",
                                         type="password",key="cana_pop_admin_password")
                if st.button("Guardar nuevo popurrí en Notion",
                             disabled=not password or not state["cana_pop_items"]):
                    if not hmac.compare_digest(password,admin_secret):
                        st.error("La clave de administración es incorrecta.")
                    else:
                        try:
                            link = notion_save(st, saved, set(song_by_id))
                            st.success("Popurrí guardado en Notion.")
                            if link:
                                st.link_button("Ver en Notion",link)
                            state["cana_pop_notion_rows"] = notion_list(
                                st, set(song_by_id))
                        except (PopurriNotionError, ValueError) as err:
                            st.error(str(err))
            else:
                st.caption("El guardado requiere configurar POPURRIS_ADMIN_PASSWORD.")

    st.divider()
    st.markdown('<div class="cana-song-title">Visor continuo</div>',
                unsafe_allow_html=True)
    st.caption("El Auto Scroll se aplica al popurrí completo, sin parar entre canciones.")
    parts=[]
    for i,item in enumerate(state["cana_pop_items"]):
        page=song_by_id[item["song_id"]]
        steps=effective_steps(item,page,mode,target,root_key)
        try:
            music=content_from_notion(item["song_id"])
        except Exception:
            st.warning("No se pudo cargar uno de los cantos. Actualiza las canciones e inténtalo nuevamente.")
            continue
        current=target_name(page,steps,root_key,notation_code)
        name=html.escape(api.song_title(page))
        parts.append(
            f'<div class="cana-pop-header">{i+1}. {name}</div>'
            f'<div class="cana-pop-subtitle">Tono: {html.escape(current)}</div>'
            +render_song(music,steps,show_chords,font_size,notation_code,
                         prevent_overlap,font_code)
        )
    if not parts:
        return
    st.markdown(CSS, unsafe_allow_html=True)
    continuous='<div class="cana-song cana-popurri-body" style="--fz:{}px">'.format(font_size)+''.join(parts)+'</div>'
    st.html(render_autoscroll_song(continuous),unsafe_allow_javascript=True)
