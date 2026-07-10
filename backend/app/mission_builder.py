"""Turns a validated MissionSpec into a real DCS .miz file using pydcs.

Static placement (units, waypoints, loadouts, weather) is done directly
through pydcs. Runtime dynamism (regenerating threats, reinforcement,
objective tracking) is layered on top via a generated MOOSE Lua script that
gets embedded into the mission's "MISSION START" trigger.

MOOSE itself is NOT bundled by this app (it's a large third-party GPLv3
project distributed by FlightControl-Master) - the caller must supply the
path to a locally-installed Moose.lua. See README for one-time setup.
"""
from __future__ import annotations

import math
import string
from pathlib import Path

import dcs
import dcs.planes as planes
import dcs.vehicles as vehicles
from dcs.action import DoScript, DoScriptFile
from dcs.mission import Mission, StartType
from dcs.task import CAP, PinpointStrike
from dcs.triggers import TriggerStart
from dcs.unit import Skill

from .mission_spec import STRIKE_TARGET_PROFILES, MissionSpec

MOOSE_TEMPLATES_DIR = Path(__file__).parent / "moose_templates"


class MissionBuildError(Exception):
    pass


def _plane_type(name: str):
    try:
        return getattr(planes, name)
    except AttributeError as e:
        raise MissionBuildError(f"Unknown aircraft type '{name}'") from e


def _vehicle_type(name: str):
    for cat in ("Armor", "AirDefence", "Unarmed", "Artillery"):
        cat_obj = getattr(vehicles, cat, None)
        if cat_obj is not None and hasattr(cat_obj, name):
            return getattr(cat_obj, name)
    raise MissionBuildError(f"Unknown vehicle type '{name}'")


def _apply_weather(m: Mission, weather: str) -> None:
    presets = {
        "clear": dict(clouds_density=0, clouds_thickness=200, clouds_base=0,
                      visibility_distance=80000, wind_at_ground=(2, 0)),
        "fair": dict(clouds_density=3, clouds_thickness=600, clouds_base=1500,
                     visibility_distance=40000, wind_at_ground=(5, 45)),
        "poor": dict(clouds_density=6, clouds_thickness=1500, clouds_base=900,
                     visibility_distance=15000, wind_at_ground=(9, 90)),
        "storm": dict(clouds_density=9, clouds_thickness=2500, clouds_base=300,
                      visibility_distance=6000, wind_at_ground=(15, 120)),
    }
    p = presets[weather]
    m.weather.clouds_density = p["clouds_density"]
    m.weather.clouds_thickness = p["clouds_thickness"]
    m.weather.clouds_base = p["clouds_base"]
    m.weather.visibility_distance = p["visibility_distance"]
    speed, direction = p["wind_at_ground"]
    m.weather.wind_at_ground.speed = speed
    m.weather.wind_at_ground.dir = direction


def _load_template(name: str, **kwargs) -> str:
    text = (MOOSE_TEMPLATES_DIR / name).read_text()
    return string.Template(text).substitute(**kwargs)


def build_mission(spec: MissionSpec, moose_lua_path: str | None = None) -> Mission:
    """Build a Mission object. Caller is responsible for m.save(path)."""
    spec.validate_whitelists()

    m = Mission(terrain=dcs.terrain.Caucasus())
    m.random_date()
    m.random_daytime(spec.time_of_day)
    _apply_weather(m, spec.weather)
    m.set_description_text(spec.briefing)
    m.sortie_text = spec.title

    terrain = m.terrain
    if spec.home_airport not in terrain.airports:
        raise MissionBuildError(f"Unknown home_airport '{spec.home_airport}' for Caucasus")
    if spec.target_airport not in terrain.airports:
        raise MissionBuildError(f"Unknown target_airport '{spec.target_airport}' for Caucasus")
    home_ap = terrain.airports[spec.home_airport]
    target_ap = terrain.airports[spec.target_airport]

    blue = m.country(spec.player_country)
    red = m.country(spec.enemy_country)

    # --- Player flight -------------------------------------------------
    maintask = CAP if spec.mission_type == "CAP" else PinpointStrike
    player_group = m.flight_group_from_airport(
        country=blue,
        name="Player Flight",
        aircraft_type=_plane_type(spec.player_aircraft),
        airport=home_ap,
        maintask=maintask,
        start_type=StartType.Cold,
        group_size=spec.player_aircraft_count,
    )
    player_group.set_client()
    for unit in player_group.units:
        unit.skill = Skill.Client
    # Send the flight toward the objective area so there's an initial route.
    objective_point = target_ap.position.point_from_heading(0, 4000)
    player_group.add_waypoint(objective_point, altitude=6000 if spec.mission_type == "CAP" else 4500)

    dynamic_lua_parts: list[str] = []

    if spec.mission_type == "CAP":
        cap_group_name = "RED CAP-1"
        cap_group = m.flight_group_from_airport(
            country=red,
            name=cap_group_name,
            aircraft_type=_plane_type(spec.enemy_air_unit),
            airport=target_ap,
            maintask=CAP,
            start_type=StartType.Cold,
            group_size=spec.enemy_air_count,
        )
        cap_group.late_activation = True

        dynamic_lua_parts.append(_load_template(
            "cap_dynamic.lua.tmpl",
            cap_template_name=cap_group_name,
            max_alive_units=spec.enemy_air_count * 2,
            max_groups=3,
            respawn_interval_seconds=600,
            target_area_name=spec.target_airport,
        ))

    else:  # STRIKE
        profile = STRIKE_TARGET_PROFILES[spec.strike_target_profile]
        target_point = target_ap.position.random_point_within(3000, 1000)
        target_group_names: list[str] = []
        total_units = 0
        for idx, (veh_name, count) in enumerate(profile):
            gname = f"STRIKE TARGET-{idx + 1}"
            vg = m.vehicle_group(
                country=red,
                name=gname,
                _type=_vehicle_type(veh_name),
                position=target_point.point_from_heading(idx * 90, 150),
                group_size=count,
            )
            target_group_names.append(vg.name)
            total_units += count

        qrf_group_name = "STRIKE QRF-1"
        qrf_group = m.vehicle_group(
            country=red,
            name=qrf_group_name,
            _type=_vehicle_type("ZSU_23_4_Shilka"),
            position=target_point.point_from_heading(180, 4000),
            group_size=2,
        )
        qrf_group.late_activation = True

        lua_names = ", ".join(f'"{n}"' for n in target_group_names)
        dynamic_lua_parts.append(_load_template(
            "strike_dynamic.lua.tmpl",
            target_group_names_lua=lua_names,
            qrf_template_name=qrf_group_name,
            qrf_trigger_threshold=math.ceil(total_units / 2),
            target_area_name=spec.target_airport,
        ))

    # --- Mission-start trigger: load MOOSE + generated dynamic logic ---
    trigger = TriggerStart(comment="Mission setup / MOOSE init")
    if moose_lua_path:
        key = m.map_resource.add_resource_file(moose_lua_path)
        trigger.add_action(DoScriptFile(key))
    trigger.add_action(DoScript(m.string(_moose_wrap("\n\n".join(dynamic_lua_parts)))))
    m.triggerrules.triggers.append(trigger)

    return m


def _moose_wrap(body: str) -> str:
    # Delay slightly so MOOSE (loaded by the preceding DoScriptFile action in
    # the same trigger) has finished initializing before our script runs.
    return (
        "local function __DcsCompanionInit()\n"
        f"{body}\n"
        "end\n"
        "if timer then\n"
        "  timer.scheduleFunction(function() __DcsCompanionInit() end, nil, timer.getTime() + 2)\n"
        "else\n"
        "  __DcsCompanionInit()\n"
        "end\n"
    )


def save_mission(spec: MissionSpec, out_path: str, moose_lua_path: str | None = None) -> str:
    m = build_mission(spec, moose_lua_path=moose_lua_path)
    m.save(out_path)
    return out_path
