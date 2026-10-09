"""API hardening: request-size limits, error handling, CORS."""
from fastapi.testclient import TestClient

from api import main
from api.main import app

client = TestClient(app)

BASE = {
    "designation": "M8",
    "grade": "ISO 8.8",
    "assembly_torque_Nmm": 20000,
    "load_cases": [{"axial_force_N": 1000, "shear_force_N": 200}],
}


def test_analyze_ok():
    r = client.post("/api/analyze", json=BASE)
    assert r.status_code == 200
    assert r.json()["case_results"]


def test_too_many_load_cases_rejected():
    body = {**BASE, "load_cases": BASE["load_cases"] * (main.MAX_LOAD_CASES + 1)}
    assert client.post("/api/analyze", json=body).status_code == 422


def test_too_many_bolts_rejected():
    body = {**BASE, "num_bolts": main.MAX_BOLTS + 1}
    assert client.post("/api/analyze", json=body).status_code == 422


def test_sweep_points_bounded():
    body = {**BASE, "sweep_points": main.MAX_SWEEP_POINTS + 1}
    assert client.post("/api/torque-window", json=body).status_code == 422
    body = {**BASE, "max_candidates": main.MAX_CANDIDATES + 1}
    assert client.post("/api/suggest-bolts", json=body).status_code == 422


def test_project_group_count_bounded():
    groups = [{"name": f"G{i}", "request": BASE} for i in range(main.MAX_GROUPS + 1)]
    r = client.post("/api/export/project-pdf", json={"groups": groups})
    assert r.status_code == 422


def test_long_strings_rejected():
    body = {**BASE, "report_meta": {"project_name": "x" * (main.MAX_TEXT + 1)}}
    assert client.post("/api/export/pdf", json=body).status_code == 422


def test_unknown_grade_is_client_error_on_pdf():
    r = client.post("/api/export/pdf", json={**BASE, "grade": "nope"})
    assert r.status_code == 400


def test_internal_errors_do_not_leak_details(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret internal path /var/task/xyz")

    monkeypatch.setattr(main, "run_vdi2230_analysis", boom)
    r = client.post("/api/analyze", json=BASE)
    assert r.status_code == 500
    assert "secret" not in r.text
    assert "/var/task" not in r.text


def test_cors_rejects_unknown_origin():
    r = client.options(
        "/api/analyze",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in r.headers
