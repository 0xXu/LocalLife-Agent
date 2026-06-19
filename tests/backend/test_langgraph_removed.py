from pathlib import Path


def test_langgraph_dependency_removed_from_pyproject():
    text = Path("pyproject.toml").read_text()
    assert "langgraph" not in text


def test_backend_production_code_does_not_import_langgraph():
    offenders = []
    for path in Path("backend").rglob("*.py"):
        text = path.read_text()
        if "langgraph" in text:
            offenders.append(str(path))
    assert offenders == []


def test_legacy_orchestrator_and_graph_modules_removed():
    assert not Path("backend/orchestrator").exists()
    assert not Path("backend/graph").exists()
