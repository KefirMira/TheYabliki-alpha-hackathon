import pytest

from services.company_news_matcher import match_news


def company(id=1, name='ООО «Синтетический маяк»', **extra):
    return dict(id=id, name=name, source_id=f'SYNTH-{id}', inn='1234567890',
                ogrn='1234567890123', aliases=[], **extra)


@pytest.mark.parametrize('text,feature', [
    ('ИНН 1234567890.', 'INN'), ('ОГРН: 1234567890123', 'OGRN'),
    ('ООО "СИНТЕТИЧЕСКИЙ МАЯК" объявило событие.', 'NAME'),
    ('«Синтетический маяк» — синтетическая публикация.', 'NAME'),
])
def test_exact_mentions(text, feature):
    result = match_news({'title': text, 'content': None}, [company()])
    assert result['status'] == 'MATCHED'
    evidence = result['candidates'][0]['evidence'][0]
    assert evidence['feature'] == feature
    assert text[evidence['start']:evidence['end']] == evidence['quote']


def test_verified_alias_and_original_unicode_offsets():
    c = company()
    c['aliases'] = [{'name': 'Синтетическая ёлочка', 'alias_id': 1,
                     'verified_by': 'synthetic reviewer', 'provenance': 'synthetic registry'}]
    text = '🌲 «Синтетическая Елочка» открылась.'
    result = match_news({'title': '', 'content': text}, [c])
    assert result['status'] == 'MATCHED'
    e = result['candidates'][0]['evidence'][0]
    assert e['quote'] == 'Синтетическая Елочка'
    assert e['names'][0]['alias_id'] == 1


@pytest.mark.parametrize('text', ['012345678901', 'x1234567890', '1234567890x',
                                 'Синтетический маяковый', 'Новость о регионе и отрасли'])
def test_boundaries_and_no_match(text):
    assert match_news({'title': text}, [company()])['status'] == 'NO_MATCH'


@pytest.mark.parametrize('name', ['Мир', 'ООО «Вектор»', 'Банк', 'Рост'])
def test_weak_names_are_not_links(name):
    result = match_news({'title': name}, [company(name=name)])
    assert result['status'] == 'AMBIGUOUS'
    assert result['matched_company_ids'] == []


def test_ambiguous_duplicate_identifier_or_name():
    for text in ('1234567890', 'Синтетический маяк'):
        result = match_news({'title': text}, [company(), company(2)])
        assert result['status'] == 'AMBIGUOUS'
        assert len(result['candidates']) == 2
        assert not result['matched_company_ids']


def test_longer_name_does_not_match_prefix_company():
    c2 = company(2, 'Синтетический маяк плюс')
    c2['inn'] = c2['ogrn'] = None
    result = match_news({'title': 'Синтетический маяк плюс'}, [company(), c2])
    assert result['matched_company_ids'] == [2]


def test_legal_form_mismatch_is_uncertain():
    assert match_news({'title': 'АО «Синтетический маяк»'}, [company()])['status'] == 'AMBIGUOUS'


def test_placeholder_and_repeatability():
    c = company(name='SYNTH-1')
    assert match_news({'title': 'SYNTH-1'}, [c])['status'] == 'NO_MATCH'
    news = {'title': '1234567890'}
    assert match_news(news, [c]) == match_news(news, [c])


def test_nested_short_name_and_full_legal_form():
    c = company(name='Общество с ограниченной ответственностью «Синтетический маяк»')
    short = company(2, name='Маяк')
    assert match_news({'title': 'ООО «Синтетический маяк»'}, [c, short])['matched_company_ids'] == [1]


def test_multiple_distinct_companies_are_independent():
    second = company(2, name='Синтетическая обсерватория')
    second['inn'] = '0123456789'
    second['ogrn'] = None
    assert match_news({'title': 'ИНН 1234567890 и 0123456789'}, [company(), second])['matched_company_ids'] == [1, 2]


def test_sentence_boundary_is_not_a_name():
    assert match_news({'title': 'Синтетический. Маяк'}, [company()])['status'] == 'NO_MATCH'


def test_full_legal_form_conflict_is_ambiguous():
    assert match_news({'title': 'Акционерное общество «Синтетический маяк»'}, [company()])['status'] == 'AMBIGUOUS'
