import zipfile

import pytest

from app.mission_builder import MissionBuildError, build_mission, save_mission
from app.mission_spec import MissionSpec

EXPECTED_MIZ_MEMBERS = {"options", "warehouses", "l10n/DEFAULT/dictionary", "l10n/DEFAULT/mapResource", "mission"}


def cap_spec(**overrides) -> MissionSpec:
    kwargs = dict(
        title="Test CAP",
        briefing="Intercept red fighters near Sochi-Adler.",
        mission_type="CAP",
        player_aircraft="F_16C_50",
        player_aircraft_count=2,
        home_airport="Kobuleti",
        target_airport="Sochi-Adler",
        enemy_air_unit="MiG_29S",
        enemy_air_count=2,
    )
    kwargs.update(overrides)
    return MissionSpec(**kwargs)


def strike_spec(**overrides) -> MissionSpec:
    kwargs = dict(
        title="Test Strike",
        briefing="Destroy the convoy near Krasnodar-Center.",
        mission_type="STRIKE",
        player_aircraft="A_10C_2",
        home_airport="Senaki-Kolkhi",
        target_airport="Krasnodar-Center",
        strike_target_profile="convoy",
    )
    kwargs.update(overrides)
    return MissionSpec(**kwargs)


def test_build_cap_mission_produces_valid_mission_object():
    m = build_mission(cap_spec())
    assert m.sortie_text == "Test CAP"
    groups = [g.name for g in m.country("USA").plane_group]
    assert "Player Flight" in groups
    red_groups = [g.name for g in m.country("Russia").plane_group]
    assert "RED CAP-1" in red_groups


def test_build_strike_mission_places_target_and_qrf():
    m = build_mission(strike_spec())
    red_vehicle_groups = [g.name for g in m.country("Russia").vehicle_group]
    assert "STRIKE TARGET-1" in red_vehicle_groups
    assert "STRIKE QRF-1" in red_vehicle_groups


def test_save_mission_writes_valid_miz(tmp_path):
    out = tmp_path / "test.miz"
    save_mission(cap_spec(), str(out))
    assert out.is_file()

    with zipfile.ZipFile(out) as z:
        assert EXPECTED_MIZ_MEMBERS.issubset(set(z.namelist()))
        mission_text = z.read("mission").decode("utf-8")
        assert "Player Flight" in mission_text
        assert "RED CAP-1" in mission_text


def test_save_mission_embeds_moose_lua_when_path_given(tmp_path):
    moose = tmp_path / "Moose.lua"
    moose.write_text("-- fake moose for test\n")
    out = tmp_path / "test_moose.miz"

    save_mission(cap_spec(), str(out), moose_lua_path=str(moose))

    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "l10n/DEFAULT/Moose.lua" in names
        mission_text = z.read("mission").decode("utf-8")
        assert "a_do_script_file" in mission_text


def test_save_mission_without_moose_lua_has_no_embedded_file(tmp_path):
    out = tmp_path / "test_no_moose.miz"
    save_mission(cap_spec(), str(out))
    with zipfile.ZipFile(out) as z:
        assert "l10n/DEFAULT/Moose.lua" not in z.namelist()


def test_strike_dynamic_lua_references_all_target_groups(tmp_path):
    out = tmp_path / "strike.miz"
    save_mission(strike_spec(), str(out))
    with zipfile.ZipFile(out) as z:
        dictionary = z.read("l10n/DEFAULT/dictionary").decode("utf-8")
        assert "STRIKE TARGET-1" in dictionary
        assert "STRIKE QRF-1" in dictionary
        assert "MISSION_OBJECTIVE_COMPLETE" in dictionary


def test_unknown_vehicle_type_raises_mission_build_error():
    from app import mission_builder

    with pytest.raises(MissionBuildError):
        mission_builder._vehicle_type("NotARealVehicle")


def test_unknown_aircraft_type_raises_mission_build_error():
    from app import mission_builder

    with pytest.raises(MissionBuildError):
        mission_builder._plane_type("NotARealPlane")
