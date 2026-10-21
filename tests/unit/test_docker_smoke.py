import json
import runpy
import subprocess
from pathlib import Path


def test_unavailable_engine_reports_the_blocker_without_creating_resources(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[2]
    main = runpy.run_path(str(root / "tests/e2e/verify_docker.py"))["main"]
    monkeypatch.setattr("sys.argv", ["verify_docker", "--output", str(tmp_path)])
    monkeypatch.setattr("shutil.which", lambda _: "docker")
    calls = []

    def unavailable(arguments, **kwargs):
        calls.append(arguments)
        raise subprocess.TimeoutExpired(arguments, 30)

    monkeypatch.setattr(subprocess, "run", unavailable)
    assert main() == 1
    assert len(calls) == 1
    assert calls[0][1] == "info"
    assert json.loads((tmp_path / "resultado.json").read_text()) == {
        "status": "blocked", "reason": "Docker engine is not responding",
        "resources_created": False,
    }
