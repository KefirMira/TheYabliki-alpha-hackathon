"""Legacy backend/test_*.py files are manual scripts, some call paid LLMs."""
collect_ignore_glob = ["backend/test_*.py"]


def pytest_ignore_collect(collection_path, config):
    """Even explicit root discovery cannot import manual scripts or venvs."""
    from pathlib import Path
    root = Path(__file__).resolve().parent
    allowed = (root / 'backend' / 'tests', root / 'parser' / 'tests')
    path = Path(collection_path).resolve()
    return not any(path == test or path in test.parents or test in path.parents for test in allowed)
