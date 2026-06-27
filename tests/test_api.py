from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALFORGE_DATABASE_URL", f"sqlite:///{tmp_path/'api.db'}")
    monkeypatch.setenv("EVALFORGE_TARGET", "mock")
    monkeypatch.setenv("EVALFORGE_JUDGE", "heuristic")
    from evalforge.api import app

    return TestClient(app)


def test_dashboard_served(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.get("/")
    assert r.status_code == 200
    assert "EvalForge" in r.text
    assert client.get("/static/app.js").status_code == 200


def test_run_list_and_gate(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    # No runs yet -> latest 404, gate 404.
    assert client.get("/runs/latest").status_code == 404
    assert client.get("/gate").status_code == 404

    created = client.post("/runs", json={}).json()
    assert created["target"] == "mock"

    runs = client.get("/runs").json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == created["run_id"]

    gate = client.get("/gate").json()
    assert "passed" in gate
    assert isinstance(gate["checks"], list)
    assert "min" in gate["thresholds"]
