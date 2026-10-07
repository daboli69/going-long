"""Parse a Fantasy Points Data Suite CSV export without altering it.

Layout seen in every real export: a sparse group row, a column row, data rows, one blank line, then a glossary of
``abbreviation,definition`` lines. Group + column names form the qualified column key (``Rushing.ATT``) because the same
abbreviation repeats across groups. Blank cells are None (missing), never 0.
"""
import csv
import hashlib
import io
import re

NUMBER = re.compile(r'-?\d+(\.\d+)?')
IDENTITY_COLUMNS = ('Rank', 'Name', 'Team', 'POS', 'G', 'Season', 'OPP', 'Location', 'Team Name')


class ParseError(ValueError):
    """The file cannot be read as a Fantasy Points export; ``code`` is stable for reports and tests."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def decode(data):
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ParseError('not_utf8', f'file is not UTF-8 text: {error}')


def qualify(groups, columns):
    """Return unique qualified keys. A repeated key inside one group gets an ordinal so nothing is overwritten."""
    keys, seen, current = [], {}, ''
    for index, column in enumerate(columns):
        current = (groups[index].strip() if groups and index < len(groups) and groups[index].strip() else current)
        key = f'{current}.{column.strip()}' if groups else column.strip()
        seen[key] = seen.get(key, 0) + 1
        keys.append(key if seen[key] == 1 else f'{key}#{seen[key]}')
    return keys


def to_number(cell):
    if NUMBER.fullmatch(cell):
        return float(cell) if '.' in cell else int(cell)
    return None


def parse_export(data):
    """Return dict(columns, groups, rows, glossary, notes). ``rows`` is a list of lists aligned to ``columns``."""
    if not data.strip():
        raise ParseError('empty', 'file is empty')
    text = decode(data)
    if '\x00' in text:
        raise ParseError('binary', 'file contains NUL bytes')
    table = list(csv.reader(io.StringIO(text, newline='')))
    if len(table) < 3:
        raise ParseError('too_short', 'fewer than a group row, a column row and one data row')
    first = table[0][0].strip() if table[0] else ''
    second = table[1][0].strip() if table[1] else ''
    two_row = len(table[1]) > 1 and second == 'Rank' and first != 'Rank'
    if two_row:
        group_row, header = table[0], table[1]
        body_start = 2
        if len(group_row) != len(header):
            raise ParseError('header_mismatch', f'group row has {len(group_row)} cells, column row has {len(header)}')
    elif first == 'Rank':
        group_row, header, body_start = None, table[0], 1
    else:
        raise ParseError('no_header', 'first rows are not a Fantasy Points header (no Rank column)')
    columns = qualify(group_row, header)
    rows, glossary, notes, line = [], {}, [], body_start
    index = body_start
    while index < len(table):
        row = table[index]
        index += 1
        if not row or all(not cell.strip() for cell in row):
            break
        if len(row) != len(header):
            raise ParseError('ragged_row', f'data row {index} has {len(row)} cells, expected {len(header)} (partial or malformed download)')
        rows.append([cell.strip() for cell in row])
    while index < len(table):
        row = table[index]
        index += 1
        if len(row) == len(header) and len(header) > 2 and any(cell.strip() for cell in row):
            raise ParseError('blank_in_data', f'data row {index} follows a blank line: rows would be silently dropped')
        if len(row) == 2 and row[0].strip():
            glossary[row[0].strip()] = row[1].strip()
    if not rows:
        raise ParseError('no_rows', 'no data rows')
    if not glossary:
        notes.append('no_glossary_footer')
    if not text.endswith(('\n', '\r')):
        notes.append('no_trailing_newline')
    return {'columns': columns, 'headers': [h.strip() for h in header], 'groups': [g.strip() for g in group_row] if group_row else None,
            'rows': rows, 'glossary': glossary, 'notes': notes}


def column_types(parsed):
    """numeric when every non-blank cell is a number, text otherwise, empty when the column has no values at all."""
    types = {}
    for position, key in enumerate(parsed['columns']):
        cells = [row[position] for row in parsed['rows'] if row[position] != '']
        types[key] = 'empty' if not cells else 'numeric' if all(NUMBER.fullmatch(cell) for cell in cells) else 'text'
    return types
