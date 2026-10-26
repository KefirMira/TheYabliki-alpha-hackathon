"""Preparation-only CLI. Fake by default; deliberately has NO --real option."""
import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from services.pilot_collection_input import registry, preflight, CollectionDraftAdapter
from services.synthetic_draft_adapter import DraftLimits
from services.pilot_collection_records import CaptureClient, prepare_record


class FakeSDK:
    def __init__(self, scenario_id):
        self.scenario_id = scenario_id
        self.chat = self.completions = self
        self.calls = 0
    def with_options(self, **options):
        assert options['max_retries']==0 and options['timeout']==60
        return self
    async def create(self, **request):
        self.calls += 1
        content = json.dumps({'relevance':'medium',
            'summary':'FAKE SDK TEST ONLY: '+self.scenario_id+' [Источник 1].',
            'risks':['Только технический тест, финансовая достоверность неизвестна [Источник 1].'],
            'opportunities':[], 'recommendations':['Нужна экспертная проверка [Источник 1].']},ensure_ascii=False)
        return {'id':'fake-test-'+self.scenario_id,'model':'fake-sdk',
            'choices':[{'finish_reason':'stop','message':{'content':content}}],
            'usage':{'prompt_tokens':1000,'completion_tokens':100,'total_tokens':1100,
                     'completion_tokens_details':{'reasoning_tokens':0}}}
    async def close(self): pass


async def fake_record(scenario_id):
    client = FakeSDK(scenario_id)
    capture = CaptureClient(client)
    adapter = CollectionDraftAdapter(capture,limits=DraftLimits(max_output_tokens=2000))
    record = await prepare_record(scenario_id,adapter,capture)
    assert client.calls == 1 and record['mode']=='FAKE_TEST_ONLY'
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--scenario')
    args = parser.parse_args()
    ids = [s['scenario_id'] for s in registry()['scenarios']]
    if args.scenario:
        if args.scenario not in ids: parser.error('scenario not allowlisted')
        ids = [args.scenario]
    if args.plan:
        result = {'mode':'PLAN_ONLY','real_calls':0,'plans':[preflight(i) for i in ids]}
    else:
        result = {'mode':'FAKE_TEST_ONLY','real_calls':0,
                  'records':[asyncio.run(fake_record(i)) for i in ids]}
    output = Path(__file__).resolve().parents[1]/'data/pilot_collection_preparation'
    output.mkdir(parents=True,exist_ok=True)
    path = output/('plan.json' if args.plan else 'fake-results.json')
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'mode':result['mode'],'scenarios':len(ids),'real_calls':0,'output':str(path)}))

if __name__=='__main__':main()
