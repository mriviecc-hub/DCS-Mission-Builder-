"""End-to-end check of the FastAPI server, with the LLM call mocked out so
the test suite doesn't require a live ANTHROPIC_API_KEY.
"""
import zipfile

from fastapi.testclient import TestClient

from app import server
from app.mission_spec import MissionSpec


def _fake_spec() -> MissionSpec:
    return MissionSpec(
        title="Dawn Patrol",
        briefing="Two F-16s hold CAP over Sochi-Adler at dawn.",
        mission_type="CAP",
        player_aircraft="F_16C_50",
        player_aircraft_count=2,
        home_airport="Kobuleti",
        target_airport="Sochi-Adler",
        enemy_air_unit="MiG_29S",
        enemy_air_count=2,
        time_of_day="dawn",
        weather="clear",
    )


def test_health():
    client = TestClient(server.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_options_lists_whitelists():
    client = TestClient(server.app)
    resp = client.get("/options")
    data = resp.json()
    assert "F_16C_50" in data["player_aircraft"]
    assert "convoy" in data["strike_target_profiles"]


def test_generate_without_api_key_falls_back_to_rule_based_parser(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out_path = tmp_path / "no_key.miz"
    client = TestClient(server.app)
    resp = client.post(
        "/generate",
        json={"prompt": "CAP over Sochi with two F-16s", "save_path": str(out_path)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["parser_used"] == "rule_based"
    assert data["spec"]["player_aircraft"] == "F_16C_50"
    assert out_path.is_file()


def test_generate_end_to_end_with_mocked_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "parse_prompt", lambda prompt, client=None: _fake_spec())

    out_path = tmp_path / "dawn_patrol.miz"
    client = TestClient(server.app)
    resp = client.post(
        "/generate",
        json={
            "prompt": "Dawn CAP over Sochi with two F-16s",
            "save_path": str(out_path),
            "anthropic_api_key": "sk-test-not-actually-used",
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["saved_path"] == str(out_path)
    assert data["spec"]["title"] == "Dawn Patrol"
    assert data["parser_used"] == "claude"

    assert out_path.is_file()
    with zipfile.ZipFile(out_path) as z:
        assert "mission" in z.namelist()
        mission_text = z.read("mission").decode("utf-8")
        assert "Player Flight" in mission_text
