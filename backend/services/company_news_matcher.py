"""Conservative, versioned exact mentions. No AI or database dependencies."""
import hashlib
import json
import re
import unicodedata

ALGORITHM_VERSION = 'exact-mentions-v1'
LEGAL_FORMS = {'ооо', 'ао', 'пао', 'оао', 'зао', 'ип'}
COMMON_NAMES = {'мир', 'рост', 'вектор', 'альфа', 'банк', 'центр', 'прогресс',
                'сервис', 'инвест', 'группа', 'технологии', 'развитие', 'компания'}
LONG_FORMS = {
    ('общество', 'с', 'ограниченной', 'ответственностью'): 'ооо',
    ('публичное', 'акционерное', 'общество'): 'пао',
    ('открытое', 'акционерное', 'общество'): 'оао',
    ('закрытое', 'акционерное', 'общество'): 'зао',
    ('акционерное', 'общество'): 'ао',
    ('индивидуальный', 'предприниматель'): 'ип',
}


def normalized(value):
    return unicodedata.normalize('NFKC', value).casefold().replace('ё', 'е')


def tokens(value):
    return [(normalized(m.group()), m.start(), m.end())
            for m in re.finditer(r'[^\W_]+', value, re.UNICODE)]


def name_tokens(value):
    parts = [t[0] for t in tokens(value)]
    for prefix in LONG_FORMS:
        if tuple(parts[:len(prefix)]) == prefix:
            return tuple(parts[len(prefix):])
    if parts and parts[0] in LEGAL_FORMS:
        parts = parts[1:]
    return tuple(parts)


def legal_form(value):
    parts = tuple(t[0] for t in tokens(value))
    if parts and parts[0] in LEGAL_FORMS:
        return parts[0]
    return next((code for prefix, code in LONG_FORMS.items() if parts[:len(prefix)] == prefix), None)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def match_news(news, companies):
    """Input catalogue is one consistent DB snapshot; offsets are Python code points.

    Any unresolved mention makes the whole run AMBIGUOUS: no automatic links.
    A name prefix inside a longer known name is not a separate mention.
    """
    names = {}
    identifiers = {}
    catalogue = sorted(companies, key=lambda c: c['id'])
    for company in catalogue:
        for kind, lengths in (('inn', (10, 12)), ('ogrn', (13, 15))):
            value = company.get(kind)
            if value and re.fullmatch(r'[0-9]+', value) and len(value) in lengths:
                identifiers.setdefault((kind, value), []).append(company['id'])
        alternatives = [{'name': company['name'], 'alias_id': None}]
        alternatives += company.get('aliases', [])
        for alias in alternatives:
            # Technical source IDs are never presented as real company names.
            if normalized(alias['name'].strip()) == normalized(company.get('source_id') or ''):
                continue
            key = name_tokens(alias['name'])
            if key:
                names.setdefault(key, []).append((company['id'], alias))
    trie = {}
    for key in names:
        node = trie
        for word in key:
            node = node.setdefault(word, {})
        node[None] = key
    findings = {}
    ambiguous = False

    def record(ids, kind, field, start, end, value, reason, aliases=None):
        nonlocal ambiguous
        uncertain = reason != 'EXACT_UNIQUE'
        ambiguous |= uncertain
        for company_id in sorted(set(ids)):
            evidence = {'feature': kind, 'field': field, 'start': start, 'end': end,
                        'quote': news[field][start:end], 'value': value, 'reason': reason}
            if aliases:
                evidence['names'] = [a for cid, a in aliases if cid == company_id]
            findings.setdefault(company_id, []).append(evidence)

    for field in ('title', 'content'):
        text = news.get(field) or ''
        for occurrence in re.finditer(r'(?<!\w)[0-9]{10,15}(?!\w)', text):
            value = occurrence.group()
            for kind in ('inn', 'ogrn'):
                ids = identifiers.get((kind, value))
                if not ids:
                    continue
                record(ids, kind.upper(), field, *occurrence.span(), value,
                       'EXACT_UNIQUE' if len(set(ids)) == 1 else 'NON_UNIQUE_IDENTIFIER')
        parts = tokens(text)
        words = tuple(p[0] for p in parts)
        occurrences = []
        for start in range(len(words)):
            node = trie
            end = start
            while end < len(words) and words[end] in node:
                node = node[words[end]]
                end += 1
                if None in node:
                    occurrences.append((start, end, node[None]))
        # Contained names (including suffixes) are not independent mentions.
        covered_until = -1
        for start, end, key in sorted(occurrences, key=lambda item: (item[0], -item[1])):
            if end <= covered_until:
                continue
            if any(not re.fullmatch(r'''[\s"'«»“”„‟\-‑–—]+''', text[parts[i][2]:parts[i + 1][1]])
                   for i in range(start, end - 1)):
                continue
            covered_until = end
            matches = names[key]
            ids = sorted({cid for cid, _ in matches})
            distinctive = (sum(map(len, key)) >= 10 and
                           (len(key) >= 2 or len(key[0]) >= 10) and
                           not all(word in COMMON_NAMES for word in key))
            reason = ('NON_UNIQUE_NAME' if len(ids) != 1 else
                      'EXACT_UNIQUE' if distinctive else 'WEAK_NAME')
            # An explicitly different legal form cannot establish an exact name.
            preceding = words[start - 1] if start else None
            for prefix, code in LONG_FORMS.items():
                if start >= len(prefix) and words[start - len(prefix):start] == prefix:
                    preceding = code
                    break
            forms = {legal_form(alias['name']) for _, alias in matches} - {None}
            if preceding in LEGAL_FORMS and forms and preceding not in forms:
                reason = 'LEGAL_FORM_MISMATCH'
            record(ids, 'NAME', field, parts[start][1], parts[start + len(key) - 1][2],
                   ' '.join(key), reason, matches)
    status = 'AMBIGUOUS' if ambiguous else 'MATCHED' if findings else 'NO_MATCH'
    by_id = {c['id']: c for c in catalogue}
    return {'status': status, 'matched_company_ids': sorted(findings) if status == 'MATCHED' else [],
            'candidates': [{'company_id': cid, 'company_snapshot': by_id[cid], 'evidence': evidence}
                           for cid, evidence in sorted(findings.items())]}
