"""Local fake SDK only. Never imports a networking SDK or reads a credential."""
import copy
import json
from types import SimpleNamespace


def response(**changes):
    raw=json.dumps({'relevance':'medium','summary':'Учебный сценарий ставки; условия займа неизвестны [Источник 1].',
        'risks':[], 'opportunities':[], 'recommendations':['Уточнить условия договора перед оценкой влияния.']},ensure_ascii=False)
    value={'choices':[{'finish_reason':'stop','message':{'content':raw}}],
           'usage':{'prompt_tokens':900,'completion_tokens':700,'total_tokens':1600,
                    'completion_tokens_details':{'reasoning_tokens':500}}}
    value.update(changes)
    return value


class FakeClient:
    def __init__(self, result=None, callback=None):
        self.result=response() if result is None else result
        self.callback=callback
        self.calls=[]
        self.options=[]
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def with_options(self, **options):
        assert options['max_retries']==0 and 0<options['timeout']<=60
        self.options.append(options)
        return self

    async def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        assert set(kwargs)=={'model','messages','max_tokens'}
        if self.callback:
            return await self.callback(kwargs)
        if isinstance(self.result,Exception):
            raise self.result
        return copy.deepcopy(self.result)
