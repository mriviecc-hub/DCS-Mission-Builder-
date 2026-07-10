"""Offline, keyword/regex-based mission parser - no LLM, no API key, no network.

Used automatically by the server when no Anthropic API key is configured.
Far less flexible than llm_parser.parse_prompt (it matches known phrases
rather than genuinely understanding the request), but it always produces a
valid MissionSpec by falling back to sensible defaults for anything it can't
confidently extract from the prompt text.
"""
from __future__ import annotations

import re

from .mission_spec import (
    CAUCASUS_BLUE_AIRPORTS,
    CAUCASUS_RED_AIRPORTS,
    ENEMY_AIR_UNITS,
    MissionSpec,
)

# --- Alias tables ------------------------------------------------------------
# Longest/most specific aliases should be checked first within each entry so
# e.g. "f/a-18" doesn't get shadowed by a looser pattern.

PLAYER_AIRCRAFT_ALIASES: dict[str, list[str]] = {
    "F_16C_50": ["f-16", "f16", "viper", "fighting falcon"],
    "FA_18C_hornet": ["f/a-18", "fa-18", "f-18", "f18", "hornet"],
    "A_10C_2": ["a-10", "a10", "warthog", "thunderbolt"],
    "F_15C": ["f-15", "f15", "eagle"],
    "M_2000C": ["mirage", "m-2000", "m2000"],
    "AV8BNA": ["av-8b", "av8b", "harrier"],
    "JF_17": ["jf-17", "jf17", "thunder"],
    "Su_25T": ["su-25", "su25", "frogfoot"],
    "MiG_29S": ["mig-29", "mig29", "fulcrum"],
    "Ka_50": ["ka-50", "ka50", "black shark", "blackshark", "werewolf"],
    "UH_1H": ["uh-1", "uh1", "huey"],
    "Su_27": ["su-27", "su27", "flanker"],
}

ENEMY_AIRCRAFT_ALIASES: dict[str, list[str]] = {
    "MiG_31": ["mig-31", "mig31", "foxhound"],
    "Su_33": ["su-33", "su33", "flanker-d", "flanker d"],
    "J_11A": ["j-11", "j11"],
    "F_5E3": ["f-5", "f5", "tiger ii", "tiger 2", "aggressor"],
    "Su_27": ["su-27", "su27", "flanker"],
    "MiG_29S": ["mig-29", "mig29", "fulcrum"],
}
assert set(ENEMY_AIRCRAFT_ALIASES) <= set(ENEMY_AIR_UNITS)

STRIKE_PROFILE_KEYWORDS: dict[str, list[str]] = {
    "sam_site": ["sam site", "sam", "air defense", "air defence", "missile site"],
    "depot": ["depot", "supply", "warehouse", "logistics"],
    "convoy": ["convoy", "trucks", "truck column", "column"],
}

CAP_KEYWORDS = ["cap", "intercept", "patrol", "dogfight", "air-to-air", "air to air", "fighter sweep"]
STRIKE_KEYWORDS = [
    "strike", "bomb", "bombing", "destroy", "attack", "cas",
    "close air support", "ground attack", "convoy", "depot", "sam site",
]

NUMBER_WORDS = {
    "one": 1, "single": 1, "solo": 1,
    "two": 2, "pair": 2, "couple": 2,
    "three": 3, "trio": 3,
    "four": 4, "flight of four": 4,
}

TIME_KEYWORDS: dict[str, list[str]] = {
    "dawn": ["dawn", "sunrise", "early morning"],
    "dusk": ["dusk", "sunset", "evening"],
    "night": ["night", "midnight", "nighttime"],
    "day": ["day", "daytime", "noon", "morning", "afternoon"],
}

WEATHER_KEYWORDS: dict[str, list[str]] = {
    "storm": ["storm", "stormy", "thunderstorm"],
    "poor": ["poor visibility", "overcast", "foggy", "fog", "rain", "rainy"],
    "fair": ["fair", "cloudy", "partly cloudy"],
    "clear": ["clear", "sunny", "clear skies"],
}

STRIKE_PROFILE_DISPLAY = {
    "convoy": "vehicle convoy",
    "sam_site": "SAM site",
    "depot": "supply depot",
}

DISPLAY_NAMES = {
    "F_16C_50": "F-16C", "FA_18C_hornet": "F/A-18C", "A_10C_2": "A-10C",
    "F_15C": "F-15C", "M_2000C": "Mirage 2000C", "AV8BNA": "AV-8B Harrier",
    "JF_17": "JF-17", "Su_27": "Su-27", "Su_25T": "Su-25T", "MiG_29S": "MiG-29S",
    "MiG_29A": "MiG-29A", "Ka_50": "Ka-50", "UH_1H": "UH-1H Huey",
    "Su_33": "Su-33", "MiG_31": "MiG-31", "J_11A": "J-11A", "F_5E3": "F-5E",
}

ALL_AIRPORTS = CAUCASUS_BLUE_AIRPORTS + CAUCASUS_RED_AIRPORTS


class RuleParseError(Exception):
    pass


def _find_alias(text: str, aliases: dict[str, list[str]]) -> str | None:
    for canonical, patterns in aliases.items():
        for pattern in sorted(patterns, key=len, reverse=True):
            if pattern in text:
                return canonical
    return None


def _find_count_near(text: str, alias: str) -> int | None:
    idx = text.find(alias)
    if idx == -1:
        return None
    window = text[max(0, idx - 25):idx]
    for word, value in sorted(NUMBER_WORDS.items(), key=lambda kv: -len(kv[0])):
        if word in window:
            return value
    m = re.search(r"([1-4])\s*x?\s*$", window)
    return int(m.group(1)) if m else None


def _find_airport(text: str, candidates: list[str]) -> str | None:
    for airport in candidates:
        key = airport.split("-")[0].lower()
        if key in text or airport.lower() in text:
            return airport
    return None


def _find_first_keyword(text: str, keyword_map: dict[str, list[str]]) -> str | None:
    for value, keywords in keyword_map.items():
        for kw in sorted(keywords, key=len, reverse=True):
            if kw in text:
                return value
    return None


def parse_prompt_rule_based(user_prompt: str) -> MissionSpec:
    text = user_prompt.lower()

    is_strike = any(kw in text for kw in STRIKE_KEYWORDS)
    is_cap = any(kw in text for kw in CAP_KEYWORDS)
    mission_type = "STRIKE" if is_strike and not is_cap else "CAP"

    player_alias_hit = None
    for canonical, patterns in PLAYER_AIRCRAFT_ALIASES.items():
        for pattern in patterns:
            if pattern in text:
                player_alias_hit = pattern
                break
        if player_alias_hit:
            player_aircraft = canonical
            break
    else:
        player_aircraft = "F_16C_50"
        player_alias_hit = None

    player_aircraft_count = (
        _find_count_near(text, player_alias_hit) if player_alias_hit else None
    ) or 1

    home_airport = _find_airport(text, CAUCASUS_BLUE_AIRPORTS) or "Kobuleti"
    target_airport = _find_airport(text, ALL_AIRPORTS)
    if target_airport is None or target_airport == home_airport:
        target_airport = "Sochi-Adler" if home_airport != "Sochi-Adler" else "Krasnodar-Center"

    time_of_day = _find_first_keyword(text, TIME_KEYWORDS) or "day"
    weather = _find_first_keyword(text, WEATHER_KEYWORDS) or "clear"

    enemy_air_unit = None
    enemy_air_count = 2
    strike_target_profile = None

    if mission_type == "CAP":
        enemy_alias_hit = None
        for canonical, patterns in ENEMY_AIRCRAFT_ALIASES.items():
            for pattern in patterns:
                if pattern in text:
                    enemy_alias_hit = pattern
                    enemy_air_unit = canonical
                    break
            if enemy_air_unit:
                break
        if enemy_air_unit is None:
            enemy_air_unit = "MiG_29S"
        else:
            enemy_air_count = _find_count_near(text, enemy_alias_hit) or 2
    else:
        strike_target_profile = _find_first_keyword(text, STRIKE_PROFILE_KEYWORDS) or "convoy"

    player_display = DISPLAY_NAMES.get(player_aircraft, player_aircraft)
    if mission_type == "CAP":
        enemy_display = DISPLAY_NAMES.get(enemy_air_unit, enemy_air_unit)
        title = f"CAP near {target_airport}"
        briefing = (
            f"{player_aircraft_count}x {player_display} flying CAP out of {home_airport} "
            f"against {enemy_air_count}x {enemy_display} operating near {target_airport}."
        )
    else:
        profile_display = STRIKE_PROFILE_DISPLAY.get(strike_target_profile, strike_target_profile)
        title = f"Strike on {target_airport}"
        briefing = (
            f"{player_aircraft_count}x {player_display} tasked to destroy a {profile_display} "
            f"near {target_airport}, launching from {home_airport}."
        )

    spec = MissionSpec(
        title=title,
        briefing=briefing,
        mission_type=mission_type,
        player_aircraft=player_aircraft,
        player_aircraft_count=min(max(player_aircraft_count, 1), 4),
        home_airport=home_airport,
        target_airport=target_airport,
        enemy_air_unit=enemy_air_unit,
        enemy_air_count=min(max(enemy_air_count, 1), 4),
        strike_target_profile=strike_target_profile,
        time_of_day=time_of_day,
        weather=weather,
    )
    spec.validate_whitelists()
    return spec
