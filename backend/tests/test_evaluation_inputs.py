import ast
from pathlib import Path

from evaluation.inputs import prepare, synthetic_chunks
from evaluation.prompts import assert_sources_unchanged, company_question, rag_messages
from evaluation.scenarios import scenarios
from schemas.company import CompanyProfile


def test_synthetic_scenarios_and_prompt_parity():
    cases = scenarios()
    assert 5 <= len(cases) <= 10 and len({c['id'] for c in cases}) == len(cases)
    assert {'macro', 'ambiguous', 'irrelevant', 'relevant'} <= {c['category'] for c in cases}
    assert_sources_unchanged()
    base = Path(__file__).resolve().parents[1] / 'services'
    tree = ast.parse((base / 'personalization_service.py').read_text(encoding='utf-8-sig'))
    expression = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'question' for t in n.targets))
    for case in cases:
        company = CompanyProfile.model_validate(case['company'])
        expected = eval(compile(ast.Expression(expression), '<production question>', 'eval'),
                        {'company_data': company.model_dump_json(indent=2, exclude_none=True), 'news': case['news']})
        assert company_question(company, case['news']) == expected
        assert case['company']['credit_exposure'] is None
    tree = ast.parse((base / 'rag_service.py').read_text(encoding='utf-8-sig'))
    expression = next(k.value for n in ast.walk(tree) if isinstance(n, ast.Call)
                      for k in n.keywords if k.arg == 'messages')
    assert rag_messages('Тест', 'Контекст') == eval(compile(ast.Expression(expression), '<production messages>', 'eval'),
                                                  {'question': 'Тест', 'context': 'Контекст'})


def test_evidence_is_exact_and_missing_context_is_explicit():
    chunks = synthetic_chunks()
    result = prepare(scenarios()[0], chunks)
    assert result['evidence'][0]['text'] == chunks[0]['text']
    assert chunks[0]['text'] in result['messages'][1]['content']
    assert prepare(scenarios()[0], [])['evidence'] == []
