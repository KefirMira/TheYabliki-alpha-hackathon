"""Closed 8-scenario registry. No DB inputs, arbitrary text, file paths or web access."""
import hashlib
import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from schemas.analysis import AnalysisContent
from services.synthetic_gateway_input import Message, canonical, SYSTEM
from services.synthetic_draft_adapter import SyntheticDraftAdapter, DraftLimits, MODEL, BASE_URL

INPUTS = Path(__file__).resolve().parents[1] / 'fixtures/pilot_collection_inputs_v1.json'
INPUTS_SHA256 = '34b6d9229bd308cecb9b8f716bfb942299e31574e4d7ffb9950f3f19d2e5492f'
PROMPT_VERSION = 'pilot-collection-v1'
PREFLIGHT = INPUTS.with_name('pilot_collection_preflight_v1.json')
PREFLIGHT_SHA256 = '48d890fa18879a7b5a2bd6bdcfe7e5fa6023e563682225d49582924eed513ed2'
COLLECTION_SYSTEM = SYSTEM + (
    ' Компания и новость синтетические. Датированные публичные источники — исторический '
    'контекст, не подтверждение учебного события или текущих условий. Не приписывай '
    'их Альфа-Банку. Отделяй цитату источника, исходные факты сценария и гипотезы. '
    'Применимость санкций и право на субсидию неизвестны; это не юридическое заключение.')


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def registry():
    raw = INPUTS.read_bytes()
    if len(raw) > 100_000:
        raise ValueError('COLLECTION_INPUT_TOO_LARGE')
    data = json.loads(raw)
    if digest(data) != INPUTS_SHA256:
        raise ValueError('COLLECTION_INPUTS_CHANGED')
    if len(data['scenarios']) != 8 or len(data['companies']) != 3:
        raise ValueError('COLLECTION_SHAPE_CHANGED')
    for source in data['sources']:
        if hashlib.sha256(source['text'].encode()).hexdigest() != source['text_sha256']:
            raise ValueError('SOURCE_EXCERPT_CHANGED')
    return data


def scenario_input(scenario_id):
    data = registry()
    selected = next((s for s in data['scenarios'] if s['scenario_id'] == scenario_id), None)
    if selected is None:
        raise ValueError('SCENARIO_NOT_ALLOWLISTED')
    company = next(c for c in data['companies'] if c['source_id'] == selected['company_id'])
    sources = {s['key']: s for s in data['sources']}
    fragments = []
    for n, key in enumerate(selected['source_keys'], 1):
        source = sources[key]
        fragments.append({'id': n, 'document': source['document'], 'page': 1,
            'chunk_id': n, 'date': source['date'], 'score': 0.0, 'text': source['text'],
            'origin_url': source['url'], 'origin_publisher': source['publisher'],
            'locator': source['locator'], 'page_is_exported_excerpt': True})
    return selected, company, fragments


class CollectionDraftInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    scenario_id: str
    fixture_sha256: str
    messages: tuple[Message, ...]


def make_collection_input(scenario_id):
    scenario, company, evidence = scenario_input(scenario_id)
    body = canonical({'synthetic_company_context': company['context'],
        'synthetic_news': {'text':scenario['news'], 'scenario_date':scenario['scenario_date']},
        'public_historical_sources': [{k:v for k,v in e.items() if k!='score'} for e in evidence], 'json_schema':AnalysisContent.model_json_schema()})
    return CollectionDraftInput(scenario_id=scenario_id, fixture_sha256=INPUTS_SHA256,
        messages=(Message(role='system',content=COLLECTION_SYSTEM),Message(role='user',content=body)))


def verify_collection_input(value):
    if type(value) is not CollectionDraftInput or value != make_collection_input(value.scenario_id):
        raise ValueError('COLLECTION_DTO_PROVENANCE_FAILED')
    result=digest(value.model_dump(mode='json'))
    plans=json.loads(PREFLIGHT.read_bytes())
    if digest(plans)!=PREFLIGHT_SHA256:
        raise ValueError('PREFLIGHT_MANIFEST_CHANGED')
    expected=next(p for p in plans['plans'] if p['scenario_id']==value.scenario_id)
    if result!=expected['dto_sha256']:
        raise ValueError('APPROVED_MESSAGES_CHANGED')
    return result


class CollectionDraftLimits(DraftLimits):
    """Collection-only opt-in; existing synthetic gateway retains its 2000 cap."""
    max_output_tokens: int = Field(default=2000, ge=1, le=4000)


class CollectionDraftAdapter(SyntheticDraftAdapter):
    """Reuse bounded existing SDK dispatch; only the pinned input boundary differs."""
    limits_type = CollectionDraftLimits

    def verify_dto(self, dto):
        return verify_collection_input(dto)


def preflight(scenario_id):
    dto = make_collection_input(scenario_id)
    scenario, company, evidence = scenario_input(scenario_id)
    allowance = len(json.dumps([m.model_dump() for m in dto.messages], ensure_ascii=False).encode()) + 512
    if allowance > 8000:
        raise ValueError('COLLECTION_INPUT_LIMIT')
    return {'scenario_id':scenario_id, 'company_id':company['source_id'],
        'fixture_sha256':INPUTS_SHA256, 'dto_sha256':verify_collection_input(dto),
        'pair_sha256':digest({'company_id':company['source_id'],'news':scenario['news']}),
        'news_sha256':hashlib.sha256(scenario['news'].encode()).hexdigest(),
        'source_sha256':[hashlib.sha256(e['text'].encode()).hexdigest() for e in evidence],
        'model':MODEL, 'base_url':BASE_URL, 'max_requests':1,
        'input_allowance':allowance, 'max_input_tokens':8000, 'max_output_tokens':2000,
        'sdk_seconds':60, 'total_seconds':120, 'retries':0, 'fallback':False,
        'cost_rub':None, 'billing_guaranteed':False, 'real_authorized':False}
