"""Lector y transpositor Caná v0.3.6 para textos musicales de Notion.

No modifica Notion. Procesa principalmente líneas de acordes amarillos
seguidas por líneas de letra blanca, tal como se editan en Cancionero Caná.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

ROOT_PATTERN = r"(?:Sol|SOL|Do|DO|Re|RE|Mi|MI|Fa|FA|La|LA|Si|SI|[A-G])(?:#|b)?"
CHORD_PATTERN = re.compile(
    rf"^(?P<root>{ROOT_PATTERN})(?P<suffix>(?:(?:maj|min|dim|aug|sus|add|m|M|ø|°|º)|[0-9#b()+-])*)"
    rf"(?:/(?P<bass>{ROOT_PATTERN}))?$"
)
SPANISH_ROOTS = {"DO": "C", "RE": "D", "MI": "E", "FA": "F", "SOL": "G", "LA": "A", "SI": "B"}
ROOT_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PREFERRED = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def root_as_english(root: str) -> str:
    match = re.fullmatch(r"(Sol|Do|Re|Mi|Fa|La|Si|[A-G])([#b]?)", root, flags=re.IGNORECASE)
    if match is None:
        raise ValueError(f"Nota no reconocida: {root}")
    note, accidental = match.groups()
    return SPANISH_ROOTS.get(note.upper(), note.upper()) + accidental


def pitch_class(root: str) -> int:
    name = root_as_english(root)
    if name[0] not in ROOT_PC:
        raise ValueError(f"Nota no reconocida: {root}")
    return (ROOT_PC[name[0]] + (name.count('#')) - name.count('b')) % 12


def transpose_root(root: str, steps: int, notation: str = 'auto') -> str:
    if notation == 'sostenidos':
        notes = SHARPS
    elif notation == 'bemoles':
        notes = FLATS
    else:
        notes = PREFERRED
    new_root = notes[(pitch_class(root) + steps) % 12]
    # Convertir la raíz, no el sufijo: lo manejamos por separado.
    if root[:2].upper() in ('DO', 'RE', 'MI', 'FA', 'LA', 'SI') or root[:3].upper() == 'SOL':
        # Conservamos notación americana como predeterminada para el visor.
        return new_root
    return new_root


def transpose_chord(chord: str, steps: int, notation: str = 'auto') -> str:
    match = CHORD_PATTERN.fullmatch(chord.strip())
    if not match:
        return chord  # Nunca inventar una interpretación de acorde dudoso
    root = transpose_root(match.group('root'), steps, notation)
    suffix = match.group('suffix') or ''
    bass = match.group('bass')
    bass_notation = notation
    if notation == 'auto':
        # En tonalidades como A, D, E o G es habitual escribir los bajos alterados
        # con sostenidos (A/C# en vez de A/Db). En Bb/Eb/Ab, bemoles.
        target_root_pc = (pitch_class(match.group('root')) + steps) % 12
        if target_root_pc in (2, 4, 7, 9, 11):
            bass_notation = 'sostenidos'
        elif target_root_pc in (1, 3, 5, 8, 10):
            bass_notation = 'bemoles'
    return root + suffix + ('/' + transpose_root(bass, steps, bass_notation) if bass else '')


# Símbolos que Notion puede incluir al pegar acordes desde documentos.
# No cambian el texto original: sólo normalizamos una COPIA para reconocerlo.
MUSICAL_EQUIVALENTS = str.maketrans({
    '♯': '#', '♭': 'b', '∕': '/', '⁄': '/', '／': '/',
    '（': '(', '）': ')', '［': '[', '］': ']',
    '：': ':', '｜': '|',
})
INVISIBLE = frozenset('\u200b\u200c\u200d\u2060\ufeff')
DECORATIONS = frozenset('|:;,-–—•·/\\')
OPENERS = '([{'
CLOSERS = ')]},;'


def _parts_of_token(raw: str, start: int):
    """Tokeniza un fragmento: (F), (C/E, Bb), Dm(F), F♯, etc.

    Guarda el índice INICIAL y FINAL original aunque haya caracteres invisibles.
    Un elemento es (inicio, fin, texto_normalizado, es_acorde).
    """
    mapping = [i for i, char in enumerate(raw) if char not in INVISIBLE]
    token = ''.join(raw[i] for i in mapping).translate(MUSICAL_EQUIVALENTS)
    if not token.strip():
        return []

    def piece(i: int, j: int, text: str, is_chord: bool):
        return (start + mapping[i], start + mapping[j - 1] + 1, text, is_chord)

    if all(c in DECORATIONS or c in OPENERS or c in CLOSERS for c in token):
        return [piece(i, i + 1, c, False) for i, c in enumerate(token)]

    # Acorde con extensión entre paréntesis: C7(b9), por ejemplo.
    if CHORD_PATTERN.fullmatch(token):
        return [piece(0, len(token), token, True)]
    # Alternativa armónica compacta: Dm(F) = Dm seguido de (F).
    compact = re.fullmatch(r'([^()]+)\(([^()]+)\)', token)
    if compact and CHORD_PATTERN.fullmatch(compact[1]) and CHORD_PATTERN.fullmatch(compact[2]):
        n = len(compact[1])
        return [piece(0, n, compact[1], True), piece(n, n + 1, '(', False),
                piece(n + 1, len(token) - 1, compact[2], True),
                piece(len(token) - 1, len(token), ')', False)]

    left = len(token) - len(token.lstrip(OPENERS))
    right = len(token) - len(token.rstrip(CLOSERS))
    limit = len(token) - right
    mid = token[left:limit]
    parts = [piece(i, i + 1, token[i], False) for i in range(left)]

    if not mid.strip():
        parts.extend(piece(i, i + 1, token[i], False) for i in range(left, limit))
    elif CHORD_PATTERN.fullmatch(mid):
        parts.append(piece(left, limit, mid, True))
    else:
        # Ejemplo compacto Dm(F): se transpone Dm y también F.
        compact = re.fullmatch(r'([^()]+)\(([^()]+)\)', mid)
        if compact and CHORD_PATTERN.fullmatch(compact[1]) and CHORD_PATTERN.fullmatch(compact[2]):
            opening = left + len(compact[1])
            parts.extend((piece(left, opening, compact[1], True),
                          piece(opening, opening + 1, '(', False),
                          piece(opening + 1, limit - 1, compact[2], True),
                          piece(limit - 1, limit, ')', False)))
        else:
            return None
    parts.extend(piece(i, i + 1, token[i], False) for i in range(limit, len(token)))
    return parts


def chord_positions(line: str) -> list[tuple[int, str]] | None:
    """Líneas compuestas por acordes y símbolos; admite paréntesis y slash chords."""
    pieces = []
    any_chord = False
    for match in re.finditer(r'\S+', line):
        parsed = _parts_of_token(match.group(), match.start())
        if parsed is None:
            return None
        pieces.extend(parsed)
        any_chord |= any(is_chord for _, _, _, is_chord in parsed)
    return [(pos, token) for pos, _, token, _ in pieces] if any_chord else None


def marked_chord_spans(chars: list[tuple[str, bool, bool, str]]) -> list[tuple[int, int, str]]:
    """Identifica sólo acordes resaltados en amarillo dentro de texto mixto.

    Por ejemplo: "2da vez ( C/E Dm7 F Bb )"; NO transpone "2da vez".
    """
    text = ''.join(item[0] for item in chars)
    result = []
    for match in re.finditer(r'\S+', text):
        raw = match.group()
        parsed = _parts_of_token(raw, match.start())
        if parsed is None:
            # Aunque el token esté pegado a signos inesperados, intentamos
            # extraer acordes completos sin modificar ninguna otra palabra.
            continue
        for start, end, candidate, is_chord in parsed:
            if not is_chord:
                continue
            if end <= len(chars) and all(chars[i][1] or chars[i][0] in INVISIBLE
                                         for i in range(start, end)):
                result.append((start, end, candidate))
    return result


@dataclass
class MusicLine:
    text: str
    yellow: bool
    kind: str = 'paragraph'
    italic: bool = False
    color: str = 'default'
    any_yellow: bool = False
    inline_chords: list[tuple[int, int, str]] = field(default_factory=list)


def text_lines(block: dict) -> list[MusicLine]:
    """Divide saltos de línea, conservando marcadores de color por carácter."""
    kind = block.get('type', '')
    content = block.get(kind, {})
    rich = content.get('rich_text', [])
    if not rich:
        return [MusicLine('', False, kind)] if kind == 'paragraph' else []
    chars: list[tuple[str, bool, bool, str]] = []
    for seg in rich:
        ann = seg.get('annotations', {})
        yellow = ann.get('color') in ('yellow', 'yellow_background')
        original_color = ann.get('color', 'default')
        for char in seg.get('plain_text', ''):
            chars.append((char, yellow, bool(ann.get('italic')), original_color))
    results: list[MusicLine] = []
    current: list[tuple[str, bool, bool, str]] = []
    for item in chars + [('\n', False, False, 'default')]:
        if item[0] == '\n':
            text = ''.join(x[0] for x in current)
            meaningful = [x for x in current if not x[0].isspace()]
            fully_yellow = bool(meaningful) and all(x[1] for x in meaningful)
            any_yellow = any(x[1] for x in meaningful)
            italic = bool(meaningful) and all(x[2] for x in meaningful)
            color = meaningful[0][3] if meaningful else 'default'
            results.append(MusicLine(text, fully_yellow, kind, italic, color,
                                     any_yellow, marked_chord_spans(current)))
            current = []
        else:
            current.append(item)
    return results


SECTION_LABELS = {'INTRO', 'VERSO', 'CORO', 'PUENTE', 'FINAL', 'ESTRIBILLO', 'REFRAN', 'REFRÁN', 'PRECORO', 'INSTRUMENTAL', 'RAP', 'OUTRO'}


def is_section(line: MusicLine) -> bool:
    title = line.text.strip().upper()
    title = title.strip(' :.-')
    section_re = r"(?:INTRO|VERSO|ESTROFA|CORO|PUENTE|FINAL|ESTRIBILLO|REFR[AÁ]N|PRE[- ]?CORO|INSTRUMENTAL|RAP|OUTRO|BIS)(?:\s+(?:[0-9]+|[IVX]+))?(?:\s*\([^)]{1,35}\))?"
    return (line.kind.startswith('heading_') or
            bool(re.fullmatch(section_re, title)) or
            line.color in ('gray', 'gray_background'))


def music_from_blocks(blocks: list[dict]) -> list[dict]:
    """Convertir bloques de Notion a renglones musicales sin cambiar los datos."""
    lines: list[MusicLine] = []
    for block in blocks:
        if block.get('type') in ('divider',):
            lines.append(MusicLine('', False, 'divider'))
            continue
        lines.extend(text_lines(block))

    items: list[dict] = []
    i = 0
    while i < len(lines):
        curr = lines[i]
        txt = curr.text
        if is_section(curr):
            items.append({'type': 'section', 'text': txt})
        elif curr.kind == 'divider':
            items.append({'type': 'blank'})
        elif not txt.strip():
            items.append({'type': 'blank'})
        elif curr.any_yellow and (positions := chord_positions(txt)):
            # Sólo emparejar si la siguiente línea NO es un acorde, encabezado o vacío.
            following = lines[i + 1] if i + 1 < len(lines) else None
            if (following is not None and following.text.strip()
                    and not is_section(following)
                    and not (following.any_yellow and chord_positions(following.text))):
                items.append({'type': 'pair', 'chords': positions, 'lyrics': following.text,
                              'italic': following.italic})
                i += 1
            else:
                items.append({'type': 'chords', 'chords': positions, 'raw': txt})
        elif curr.inline_chords:
            items.append({'type': 'inline_annotation', 'text': txt,
                          'chords': curr.inline_chords, 'italic': curr.italic})
        else:
            items.append({'type': 'text', 'text': txt, 'italic': curr.italic,
                          'unparsed_yellow': curr.any_yellow})
        i += 1
    return items


def _group_parentheses(tokens: list[tuple[int, str]]) -> list[tuple[int, str, bool]]:
    """Mantiene juntos los acordes opcionales entre paréntesis.

    Si (C/E Dm7) pasa a (D/F# Em7), desplaza sólo los elementos interiores
    indispensables; nunca altera la letra inferior.
    """
    result: list[tuple[int, str, bool]] = []
    i = 0
    while i < len(tokens):
        pos, label = tokens[i]
        if label != '(':
            result.append((pos, label, bool(CHORD_PATTERN.fullmatch(label))))
            i += 1
            continue
        depth = 1
        j = i + 1
        while j < len(tokens):
            if tokens[j][1] == '(':
                depth += 1
            elif tokens[j][1] == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0:  # Paréntesis incompleto: conservarlo como texto.
            result.append((pos, '(', False))
            i += 1
            continue
        group = tokens[i:j + 1]
        new_positions: list[tuple[int, str]] = []
        cursor = pos
        previous_chord = False
        for original_pos, item in group:
            current_chord = bool(CHORD_PATTERN.fullmatch(item))
            gap = 1 if previous_chord and current_chord else 0
            placed_pos = max(original_pos, cursor + gap)
            new_positions.append((placed_pos, item))
            cursor = placed_pos + len(item)
            previous_chord = current_chord
        length = cursor - pos
        rendered = [' '] * length
        for placed_pos, item in new_positions:
            rendered[placed_pos - pos: placed_pos - pos + len(item)] = list(item)
        result.append((pos, ''.join(rendered), False))
        i = j + 1
    return result


def aligned_tracks(chords: list[tuple[int, str]], lyrics: str | None,
                   steps: int, notation: str = 'auto',
                   prevent_overlap: bool = True) -> tuple[list[str], str]:
    """Dibuja las columnas originales sin mover la letra y agrupa paréntesis.

    Los acordes que chocan pueden ocupar otra fila; los paréntesis siempre
    permanecen unidos a los acordes alternativos que encierran.
    """
    tokens = [(max(0, int(pos)), transpose_chord(ch, steps, notation)) for pos, ch in chords]
    tokens.sort(key=lambda item: item[0])
    lyric = (lyrics or '').expandtabs(4)
    rendered_tokens = _group_parentheses(tokens)
    tracks: list[list[tuple[int, str, bool]]] = []
    for pos, label, is_chord in rendered_tokens:
        for track in tracks:
            def no_collision(earlier):
                epos, etext, echord = earlier
                sep = 1 if echord and is_chord else 0
                return pos >= epos + len(etext) + sep or epos >= pos + len(label) + sep
            if not prevent_overlap or all(no_collision(other) for other in track):
                track.append((pos, label, is_chord))
                break
        else:
            tracks.append([(pos, label, is_chord)])
    rows = []
    for track in tracks:
        width = max([0] + [pos + len(label) for pos, label, _ in track])
        chars = [' '] * width
        for pos, label, _ in track:
            chars[pos:pos + len(label)] = list(label)
        rows.append(''.join(chars).rstrip())
    return rows, lyric


def styled_lyrics(text: str) -> str:
    """Solo resalta la indicación BIS; el resto de la letra sigue blanco.

    Escapa primero el texto de Notion para no permitir HTML arbitrario.
    El span no cambia el ancho de las palabras ni los espacios monoespaciados.
    """
    safe = html.escape(text)
    return re.sub(r'(?<!\w)(BIS)(?!\w)',
                  r'<span class="cana-repetition">\1</span>', safe, flags=re.IGNORECASE)


def highlight_delimiters(text: str) -> str:
    # Escape antes de crear etiquetas para que Notion nunca inserte HTML activo.
    escaped = html.escape(text)
    return re.sub(r'([()])', r'<span class="cana-delimiter">\1</span>', escaped)



def render_anchored_pair(chord_rows: list[str], lyrics: str, italic: bool = False) -> str | None:
    """Acordes encima de las letras usando anclas reales, no espacios de fuente proporcional.

    La columna de Notion indica un índice de carácter; el acorde se ancla a
    esa letra en vez de hacer coincidir dos líneas de anchuras diferentes.
    Si el acorde supera el final de la letra, devolvemos None y usamos
    la representación monoespaciada exacta para ese par.
    """
    if not lyrics:
        return None
    anchors: dict[int, list[tuple[int, str]]] = {}
    for row_index, row in enumerate(chord_rows):
        # Conserva cualquier progresión entre paréntesis como una unidad.
        for match in re.finditer(r'\([^)]*\)|\S+', row):
            if match.start() >= len(lyrics):
                return None
            anchors.setdefault(match.start(), []).append((len(chord_rows)-row_index, match.group()))
    bis_spots: set[int] = set()
    for match in re.finditer(r'(?<!\w)BIS(?!\w)', lyrics, flags=re.IGNORECASE):
        bis_spots.update(range(match.start(), match.end()))
    body = []
    for i, ch in enumerate(lyrics):
        safe = html.escape(ch)
        if i in bis_spots:
            safe = f'<span class="cana-repetition">{safe}</span>'
        if i in anchors:
            notes = ''.join(
                f'<span class="cana-float-chord" style="--note-row:{row_number}">{highlight_delimiters(label)}</span>'
                for row_number, label in anchors[i]
            )
            body.append(f'<span class="cana-note-anchor">{notes}{safe}</span>')
        else:
            body.append(safe)
    italic_class = ' cana-italic' if italic else ''
    return (f'<div class="cana-anchored-pair" style="--chord-rows:{len(chord_rows)}">'
            f'<div class="cana-lyric cana-anchored-lyrics{italic_class}">{"".join(body)}</div>'
            f'</div>')


def render_song(items: list[dict], steps: int = 0, show_chords: bool = True,
                font_size: int = 17, notation: str = 'auto',
                prevent_overlap: bool = True, font_style: str = 'mono') -> str:
    size = min(34, max(13, int(font_size)))
    font_style = font_style if font_style in ('mono', 'comic', 'futura', 'helvetica') else 'mono'
    parts = [f'<div class="cana-song cana-font-{font_style}" style="--fz:{size}px">']
    for item in items:
        typ = item['type']
        if typ == 'blank':
            parts.append('<div class="cana-blank"></div>')
        elif typ == 'section':
            parts.append(f'<div class="cana-section">{styled_lyrics(item["text"])}</div>')
        elif typ == 'text':
            warning_class = ' cana-unknown' if item.get('unparsed_yellow') else ''
            italic_class = ' cana-italic' if item.get('italic') else ''
            parts.append(f'<div class="cana-lyric{warning_class}{italic_class}">{styled_lyrics(item["text"])}</div>')
        elif typ == 'inline_annotation':
            # Texto y acordes en una misma línea. No altera la letra normal.
            content, last = [], 0
            for start, end, chord in item['chords']:
                content.append(styled_lyrics(item['text'][last:start]))
                if show_chords:
                    content.append('<span class="cana-inline-chord">' +
                                   html.escape(transpose_chord(chord, steps, notation)) + '</span>')
                last = end
            content.append(styled_lyrics(item['text'][last:]))
            italic_class = ' cana-italic' if item.get('italic') else ''
            parts.append(f'<div class="cana-lyric{italic_class}">{"".join(content)}</div>')
        elif typ in ('pair', 'chords'):
            lyric = item.get('lyrics') if typ == 'pair' else None
            chord_rows, aligned_lyric = aligned_tracks(item['chords'], lyric, steps, notation,
                                                       prevent_overlap)
            # Para fuentes proporcionales, anclamos cada acorde al carácter
            # original de Notion. Mono conserva exactamente el formato probado.
            anchored = (render_anchored_pair(chord_rows, aligned_lyric, item.get('italic', False))
                        if (typ == 'pair' and show_chords and font_style != 'mono') else None)
            if anchored:
                parts.append(anchored)
            else:
                if show_chords:
                    for chord_row in chord_rows:
                        parts.append(f'<div class="cana-chordline">{highlight_delimiters(chord_row)}</div>')
                if typ == 'pair':
                    italic_class = ' cana-italic' if item.get('italic') else ''
                    fallback_class = ' cana-force-mono' if (font_style != 'mono' and show_chords) else ''
                    parts.append(f'<div class="cana-lyric{italic_class}{fallback_class}">{styled_lyrics(aligned_lyric)}</div>')
                elif show_chords:
                    parts.append('<div class="cana-progression-gap"></div>')
            if typ == 'pair':
                parts.append('<div class="cana-verse-gap"></div>')
    parts.append('</div>')
    return ''.join(parts)


CSS = """
<style>
.cana-song {color:#f2f2f4; font-family:Consolas, 'Courier New', monospace;
            font-size:var(--fz); line-height:1.36; overflow-x:auto;
            background:#191b20; border-radius:14px; padding:24px 20px 36px;
            border:1px solid #353740; font-variant-ligatures:none;
            font-feature-settings:'liga' 0;}
.cana-song .cana-chordline {color:#ffce58; font-weight:750; white-space:pre;
                           font-family:inherit; tab-size:4; width:max-content;}
.cana-song .cana-delimiter {color:#a5a8b3; font-weight:500;}
.cana-song .cana-inline-chord {color:#ffce58; font-weight:750;}
.cana-song .cana-lyric {color:#f2f2f4; white-space:pre; tab-size:4; width:max-content;
                       font-family:inherit;}
/* Tipografías opcionales únicamente dentro del visor musical. */
.cana-font-comic .cana-lyric:not(.cana-force-mono) {font-family:'Comic Sans MS','Comic Sans',cursive;}
.cana-font-futura .cana-lyric:not(.cana-force-mono) {font-family:Futura,'Trebuchet MS',sans-serif;}
.cana-font-helvetica .cana-lyric:not(.cana-force-mono) {font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;}
.cana-song .cana-force-mono {font-family:Consolas,'Courier New',monospace;}
/* Las anclas mantienen los acordes encima del carácter de Notion aun con letras
   proporcionales. Nunca insertamos espacios en el texto de la canción. */
.cana-song .cana-anchored-pair {padding-top:calc(var(--chord-rows) * 1.37em); position:relative; width:max-content;}
.cana-song .cana-anchored-lyrics {font-size:inherit; line-height:1.36; white-space:pre;}
.cana-song .cana-note-anchor {position:relative; display:inline;}
.cana-song .cana-float-chord {
    position:absolute; left:0; bottom:calc(var(--note-row) * 1.37em);
    font-family:Consolas,'Courier New',monospace !important; font-style:normal;
    font-size:inherit; line-height:1.20; color:#ffce58; font-weight:750;
    white-space:pre; width:max-content; pointer-events:none;
}

.cana-song .cana-italic {font-style:italic;}
.cana-song .cana-unknown {color:#ffce58;}
.cana-song .cana-verse-gap {height:.70em;}
.cana-song .cana-progression-gap {height:1.15em;}
.cana-song .cana-section {color:#adc2fa; font-size:.81em; font-weight:750;
                          letter-spacing:.055em; margin:20px 0 11px; white-space:pre;}
.cana-song .cana-repetition {color:#adc2fa; font-weight:800;}
.cana-song .cana-blank {height:.65em;}
@media (max-width:640px) {.cana-song {padding:16px 12px 25px;}}
</style>
"""
