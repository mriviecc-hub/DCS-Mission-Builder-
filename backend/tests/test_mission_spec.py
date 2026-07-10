import pytest
from pydantic import ValidationError

from app.mission_spec import MissionSpec


def _base_kwargs(**overrides):
    kwargs = dict(
        title="Test",
        briefing="Test briefing.",
        mission_type="CAP",
        player_aircraft="F_16C_50",
        home_airport="Kobuleti",
        target_airport="Sochi-Adler",
        enemy_air_unit="MiG_29S",
    )
    kwargs.update(overrides)
    return kwargs


def test_valid_cap_spec_builds():
    spec = MissionSpec(**_base_kwargs())
    spec.validate_whitelists()
    assert spec.mission_type == "CAP"


def test_valid_strike_spec_builds():
    spec = MissionSpec(**_base_kwargs(
        mission_type="STRIKE", enemy_air_unit=None, strike_target_profile="convoy",
    ))
    spec.validate_whitelists()


def test_rejects_unknown_aircraft():
    with pytest.raises(ValidationError):
        MissionSpec(**_base_kwargs(player_aircraft="F_22A_Raptor"))


def test_rejects_unknown_airport():
    with pytest.raises(ValidationError):
        MissionSpec(**_base_kwargs(home_airport="Nellis AFB"))


def test_rejects_home_airport_on_red_side():
    # home_airport is restricted to the blue-friendly whitelist even though
    # it's a valid Caucasus airport in general (it's red-friendly).
    with pytest.raises(ValidationError):
        MissionSpec(**_base_kwargs(home_airport="Anapa-Vityazevo"))


def test_cap_without_enemy_air_unit_fails_whitelist_check():
    spec = MissionSpec(**_base_kwargs(enemy_air_unit=None))
    with pytest.raises(ValueError):
        spec.validate_whitelists()


def test_strike_without_target_profile_fails_whitelist_check():
    spec = MissionSpec(**_base_kwargs(mission_type="STRIKE", enemy_air_unit=None))
    with pytest.raises(ValueError):
        spec.validate_whitelists()
