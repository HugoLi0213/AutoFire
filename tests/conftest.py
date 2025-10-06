import pytest

@pytest.fixture(autouse=True)
def add_project_root_to_path(monkeypatch):
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    monkeypatch.syspath_prepend(str(project_root))
