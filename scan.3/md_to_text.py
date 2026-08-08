"""Turn the Markdown docs into plain text for the application folder.

Markdown is right for GitHub, which renders it, and wrong for a folder someone
opens on their own PC: Windows has no default handler for .md, so it opens in
a browser or not at all, while .txt opens in Notepad immediately.

Renaming the file is not enough. Read as plain text, Markdown is full of
syntax that only makes sense rendered -- hashes, asterisks, pipe tables,
bracketed links -- so this converts rather than copies. Headings become
underlined, tables become aligned columns, and link targets are kept only when
they point somewhere a reader could actually go.

Output uses CRLF, because these files are written for Notepad.
"""
from __future__ import annotations

import re

BULLET = '  - '
INDENT = '    '


def _inline(text: str) -> str:
    """Strip inline markup, keeping useful link targets."""
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # An in-page anchor cannot be followed in a text file, so it becomes a
    # quoted section name -- "read 'Before you trade real money' at the
    # bottom" still tells the reader exactly where to go, where the bare
    # words would run into the surrounding sentence.
    text = re.sub(r'\[([^\]]+)\]\(#[^)]*\)', r'"\1"', text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'\1 (\2)', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\*\*\*([^*]+)\*\*\*', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_([^_]+)_(?!_)', r'\1', text)
    return text


def _table(rows: list) -> list:
    """Pipe table to aligned columns."""
    cells = []
    for row in rows:
        stripped = row.strip().strip('|')
        parts = [_inline(p.strip()) for p in stripped.split('|')]
        # The |---|---| separator carries no content.
        if all(re.fullmatch(r':?-{2,}:?', p.strip()) for p in parts if p.strip()):
            continue
        cells.append(parts)
    if not cells:
        return []

    columns = max(len(r) for r in cells)
    cells = [r + [''] * (columns - len(r)) for r in cells]
    widths = [max(len(r[i]) for r in cells) for i in range(columns)]

    out = []
    for index, row in enumerate(cells):
        out.append('  ' + '   '.join(
            value.ljust(widths[i]) for i, value in enumerate(row)).rstrip())
        if index == 0:               # underline the header row
            out.append('  ' + '   '.join('-' * w for w in widths))
    return out


def convert(markdown: str) -> str:
    lines = markdown.replace('\r\n', '\n').split('\n')
    out: list = []
    table: list = []
    in_code = False

    def flush_table():
        if table:
            out.extend(_table(table))
            table.clear()

    for line in lines:
        if line.startswith('```'):
            flush_table()
            in_code = not in_code
            continue
        if in_code:
            out.append(INDENT + line)
            continue

        if line.lstrip().startswith('|') and line.count('|') >= 2:
            table.append(line)
            continue
        flush_table()

        heading = re.match(r'^(#{1,6})\s+(.*)$', line)
        if heading:
            level, text = len(heading.group(1)), _inline(heading.group(2))
            if out and out[-1] != '':
                out.append('')
            if level == 1:
                text = text.upper()
                out.extend([text, '=' * len(text)])
            elif level == 2:
                out.extend([text, '-' * len(text)])
            else:
                out.append(text)
            continue

        if re.fullmatch(r'\s*([-*_])\s*\1\s*\1[\s\-*_]*', line):
            out.append('-' * 70)
            continue

        # A link definition such as [1.0.0]: https://... is only useful as
        # the bare address once the brackets stop meaning anything.
        definition = re.match(r'^\[([^\]]+)\]:\s*(\S+)\s*$', line)
        if definition:
            out.append(f'{definition.group(1)}: {definition.group(2)}')
            continue

        bullet = re.match(r'^(\s*)[-*+]\s+(.*)$', line)
        if bullet:
            lead = ' ' * len(bullet.group(1))
            out.append(f'{lead}{BULLET}{_inline(bullet.group(2))}')
            continue

        numbered = re.match(r'^(\s*)(\d+)\.\s+(.*)$', line)
        if numbered:
            lead = ' ' * len(numbered.group(1))
            out.append(f'{lead}  {numbered.group(2)}. {_inline(numbered.group(3))}')
            continue

        out.append(_inline(line))

    flush_table()

    # Collapse the runs of blank lines the headings introduce.
    text: list = []
    for line in out:
        if line.strip() == '' and text and text[-1].strip() == '':
            continue
        text.append(line.rstrip())
    return '\r\n'.join(text).strip('\r\n') + '\r\n'


def convert_file(source, destination) -> None:
    from pathlib import Path

    source, destination = Path(source), Path(destination)
    # utf-8-sig writes a byte-order mark. These files contain em dashes, a
    # pound sign and curly quotes, and the mark is what stops an editor that
    # guesses at encoding from rendering those as mojibake. Notepad and every
    # other Windows editor read it correctly.
    destination.write_text(convert(source.read_text(encoding='utf-8')),
                           encoding='utf-8-sig', newline='')
