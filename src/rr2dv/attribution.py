"""Source-definition credits for the content actually selected for conversion."""
import copy
import re

PUBLISHER = 'Giraffe Labs LLC'
RIGHTS_NOTICE = 'All models remain the property of their existing rights holders.'


def artists(text, name=''):
    """Keep supplied names and spelling; asset-title placeholders are not people."""
    if not isinstance(text, str) or not text.strip():
        return []
    text = text.strip()
    name = name if isinstance(name, str) else ''
    title = re.sub(r'^[A-Z]-\d+[A-Z]?\s+', '', name).strip()
    if text.casefold() in {name.strip().casefold(), title.casefold()}:
        return []
    if ':' in text:
        prefix, rest = text.split(':', 1)
        words = set(re.findall(r'[a-z]+', prefix.lower()))
        if words and words <= {'model', 'models', 'texture', 'textures', 'and', 'art',
                              'animation', 'animations', 'sound', 'audio', 'music', 'modelling', 'modeling'}:
            text = rest.strip()
    return list(dict.fromkeys(s.strip() for s in re.split(r',|;|&|\band\b|\n', text) if s.strip()))


def content(identifier, name, role, pack, credit_fields):
    names = list(dict.fromkeys(person for text, title in credit_fields for person in artists(text, title)))
    return {'id': identifier, 'name': name or identifier, 'role': role, 'pack': pack,
            'credits': names, 'attribution': ', '.join(names) if names else PUBLISHER,
            'creditText': list(dict.fromkeys(text.strip() for text, _ in credit_fields if isinstance(text, str) and text.strip()))}


def source(contents, packs):
    return {'id': 'Railroader (base game asset packs)', 'kind': 'game', 'root': '', 'path': '',
            'credits': list(dict.fromkeys(n for item in contents for n in item['credits'])),
            'contentCredits': contents, 'publisher': PUBLISHER, 'rightsNotice': RIGHTS_NOTICE,
            'packs': packs}


def source_label(source):
    names = list(source.get('credits') or [])
    if 'contentCredits' in source and (not source['contentCredits'] or any(not c['credits'] for c in source['contentCredits'])):
        if PUBLISHER not in names:
            names.append(PUBLISHER)
    return source['id'] + (f" (credited: {', '.join(names)})" if names else '')


def source_labels(sources):
    """The same per-content attribution is used by review, notice and provenance."""
    lines = []
    for source in sources:
        if 'contentCredits' not in source:
            lines.append(source_label(source))
            continue
        lines.append(source['id'])
        lines.extend(f"{item['name']} ({item['role']}): {item['attribution']}" for item in source['contentCredits'])
        if not source['contentCredits']:
            lines.append(PUBLISHER)
    if any('contentCredits' in source for source in sources):
        lines.append(RIGHTS_NOTICE)
    return lines


def preview_whistle(sources, selected):
    """A dropdown preview cannot mutate the inventory used by the conversion."""
    result = copy.deepcopy(sources)
    for source in result:
        if 'contentCredits' not in source:
            continue
        items = source['contentCredits']
        source['contentCredits'] = [item for item in items if item['role'] != 'whistle definition and mesh'] + [copy.deepcopy(selected)]
        source['credits'] = list(dict.fromkeys(n for item in source['contentCredits'] for n in item['credits']))
    return result
