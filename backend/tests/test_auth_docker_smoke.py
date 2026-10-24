"""Check Docker smoke contracts without contacting Docker, a provider or real data."""
import copy
from pathlib import Path
import runpy

import pytest

from main import app

SMOKE = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'docker/smoke.py'))


def test_smoke_checks_actual_routes_and_accepts_additions():
    spec = copy.deepcopy(app.openapi())
    SMOKE['check_spec'](spec)
    spec['paths']['/synthetic-extra'] = {'get': {}}
    SMOKE['check_spec'](spec)


@pytest.mark.parametrize('change', ['missing_capabilities', 'wrong_method', 'missing_acl', 'missing_503'])
def test_smoke_rejects_missing_capability_contract(change):
    spec = copy.deepcopy(app.openapi())
    path = '/api/companies/{source_id}/capabilities'
    if change == 'missing_capabilities':
        spec['paths']['/synthetic-wrong-route'] = spec['paths'].pop(path)
    elif change == 'wrong_method':
        spec['paths'][path]['post'] = spec['paths'][path].pop('get')
    elif change == 'missing_acl':
        spec['paths'][path]['get'].pop('security')
    else:
        spec['paths'][path]['get']['responses'].pop('503')
    with pytest.raises((KeyError, AssertionError)):
        SMOKE['check_spec'](spec)
