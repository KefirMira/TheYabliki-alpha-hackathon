"""Conservative document projection; a filename proves neither format nor publisher."""
from pathlib import PurePosixPath


def source_metadata(document):
    suffix = PurePosixPath((document or '').lower()).suffix
    return {
        'declared_format': {'.txt': 'TXT', '.pdf': 'PDF'}.get(suffix, 'UNKNOWN'),
        'format_verified': False,
        'publisher': None,
        'attribution_status': 'UNKNOWN',
    }


def card_provenance(sources, evidence):
    # Do not modify history in PostgreSQL. Preserve source fields and identifiers.
    projected = [{**source, 'provenance': source.get('provenance', source_metadata(source.get('document')))} for source in sources]
    rows = []
    for evidence_row in evidence:
        row = dict(evidence_row)
        # Legacy PDF alone is not proof. Preserve independently verified format
        # only for this exact fragment; never borrow provenance from a neighbour.
        # Format verification says nothing about who published the document.
        if row['evidence_type'] == 'PDF' and not verified_pdf(sources, row):
            row['evidence_type'] = 'DOCUMENT'
        rows.append(row)
    return projected, rows


def verified_pdf(sources, evidence):
    identity = tuple(evidence.get(key) for key in ('document', 'page', 'chunk_id'))
    if not identity[0] or identity[1] is None or identity[2] is None:
        return False
    matching = [source for source in sources if
                tuple(source.get(key) for key in ('document', 'page', 'chunk_id')) == identity]
    return bool(matching) and all(
        isinstance(source.get('provenance'), dict)
        and source['provenance'].get('format_verified') is True
        and source['provenance'].get('declared_format') == 'PDF'
        for source in matching
    )
