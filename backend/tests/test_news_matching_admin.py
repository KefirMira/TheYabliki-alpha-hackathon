import argparse
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

import news_matching_admin as cli


@pytest.mark.parametrize('argv', [[], ['match', '--news-id', '1'],
    ['show', '--news-id', '0'], ['show', '--news-id', '1', '--run-id', '-1'],
    ['match', '--news-id', '1', '--run-id', '2', '--confirm-write']])
def test_cli_requires_explicit_single_news(argv):
    with pytest.raises(SystemExit):
        cli.arguments(argv)


@pytest.mark.parametrize('action', ['match', 'show'])
def test_cli_delegates_to_service(monkeypatch, action):
    service = AsyncMock()
    service.match.return_value = service.show.return_value = {'status': 'NO_MATCH'}
    monkeypatch.setattr(cli, 'NewsMatchingService', lambda sessions: service)
    args = argparse.Namespace(action=action, news_id=7, run_id=3)
    assert asyncio.run(cli.execute(args, object())) == {'status': 'NO_MATCH'}
    if action == 'match':
        service.match.assert_awaited_once_with(7)
        service.show.assert_not_awaited()
    else:
        service.show.assert_awaited_once_with(7, 3)
        service.match.assert_not_awaited()


def test_cli_configuration_error_is_sanitized(monkeypatch, capsys):
    async def fail(args):
        raise RuntimeError('secret DSN and article content')
    monkeypatch.setattr(cli, 'main_async', fail)
    assert cli.main(['show', '--news-id', '1']) == 1
    assert json.loads(capsys.readouterr().out) == {'code': 'MATCHING_DATABASE_OR_CONFIGURATION_ERROR'}


def test_matching_is_not_a_public_route():
    from main import app
    assert all('matching' not in path and 'match-runs' not in path for path in app.openapi()['paths'])
