"""Turns a plain-English mission request into a validated MissionSpec.

Uses Claude's structured-outputs support (client.messages.parse) so the
response is guaranteed to match the MissionSpec JSON schema - including every
Literal-typed field, which the LLM literally cannot fill with a value outside
the DCS-asset whitelist.
"""
from __future__ import annotations

import anthropic

from .mission_spec import (
    ALL_CAUCASUS_AIRPORTS,
    CAUCASUS_BLUE_AIRPORTS,
    ENEMY_AIR_UNITS,
    PLAYER_AIRCRAFT,
    STRIKE_TARGET_PROFILES,
    MissionSpec,
)

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = f"""You are a DCS World (Digital Combat Simulator) mission designer. \
Convert the user's plain-English request into a structured mission for the \
Caucasus theater, Blue coalition player, with a CAP (combat air patrol / \
intercept) or STRIKE (ground attack) mission type.

Guidance for filling fields:
- Pick whichever mission_type best matches the request. If the user asks to \
"intercept", "dogfight", "patrol", or fight enemy aircraft, use CAP. If they \
ask to destroy, bomb, or strike ground targets (vehicles, convoys, depots, \
SAM sites), use STRIKE.
- player_aircraft must be one of: {", ".join(PLAYER_AIRCRAFT)}. Pick the one \
that best matches what the user asked for (e.g. "F-16" -> F_16C_50, "Hornet" \
or "F/A-18" -> FA_18C_hornet, "Warthog" or "A-10" -> A_10C_2, "Hind"/"Hip" \
helicopters aren't available - substitute Ka_50 or UH_1H only if the user \
explicitly asked for a helicopter). Default to F_16C_50 if unspecified.
- home_airport must be one of: {", ".join(CAUCASUS_BLUE_AIRPORTS)}. Pick \
whichever is geographically reasonable, or Kobuleti by default.
- target_airport must be one of: {", ".join(ALL_CAUCASUS_AIRPORTS)}. This \
anchors where the enemy threat/target spawns - pick the one nearest to \
wherever the user describes the objective (e.g. "near Sochi" -> \
Sochi-Adler). Default to a Russian-side airport if the user gives no \
location.
- For CAP missions, enemy_air_unit must be one of: {", ".join(ENEMY_AIR_UNITS)}.
- For STRIKE missions, strike_target_profile must be one of: \
{", ".join(STRIKE_TARGET_PROFILES.keys())} (convoy = trucks + AAA escort, \
sam_site = command vehicle + AAA + short-range SAM, depot = static supply \
trucks, no escort).
- Write a punchy 1-3 sentence pilot briefing in the briefing field.
- Infer time_of_day and weather from mood/atmosphere words in the request \
("dawn raid", "stormy night intercept") - default to day/clear if unstated.
"""


class ParseError(Exception):
    pass


def parse_prompt(user_prompt: str, client: anthropic.Anthropic | None = None) -> MissionSpec:
    client = client or anthropic.Anthropic()

    response = client.messages.parse(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        output_format=MissionSpec,
    )

    if response.stop_reason == "refusal":
        raise ParseError("Claude declined to generate this mission (safety refusal).")
    if response.parsed_output is None:
        raise ParseError(f"Claude did not return a parseable mission spec (stop_reason={response.stop_reason}).")

    spec = response.parsed_output
    spec.validate_whitelists()
    return spec
