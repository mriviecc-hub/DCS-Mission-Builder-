"""Structured mission specification.

This is the contract between the natural-language parser (llm_parser.py) and
the pydcs mission builder (mission_builder.py). Every field that maps to a
concrete DCS asset (aircraft, vehicle, airport) is restricted to a whitelist
so the builder never has to guess at, or fail on, a hallucinated unit name.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --- Whitelists -------------------------------------------------------------
# Kept intentionally small for v1 (Caucasus / Blue / CAP & Strike). Extend as
# more theaters and mission types come online.

PLAYER_AIRCRAFT = [
    "F_16C_50",
    "FA_18C_hornet",
    "A_10C_2",
    "F_15C",
    "M_2000C",
    "AV8BNA",
    "JF_17",
    "Su_27",
    "Su_25T",
    "MiG_29S",
    "Ka_50",
    "UH_1H",
]

ENEMY_AIR_UNITS = [
    "MiG_29S",
    "MiG_29A",
    "Su_27",
    "Su_33",
    "MiG_31",
    "J_11A",
    "F_5E3",
]

# Named ground-target compositions for STRIKE missions. Each maps to a list
# of (pydcs vehicle class name, count) built around the target point.
STRIKE_TARGET_PROFILES: dict[str, list[tuple[str, int]]] = {
    "convoy": [("Ural_375", 4), ("ZSU_23_4_Shilka", 1)],
    "sam_site": [("Ural_375", 1), ("ZSU_23_4_Shilka", 1), ("Osa_9A33_ln", 1)],
    "depot": [("Ural_375", 6)],
}

BLUE_COUNTRIES = ["USA", "UK", "Germany", "France", "Israel", "Georgia"]
RED_COUNTRIES = ["Russia", "USAFAggressors"]

# Caucasus airfields, split roughly by traditional faction friendliness for
# sane defaults. The builder validates against pydcs's own terrain object too.
CAUCASUS_BLUE_AIRPORTS = [
    "Kobuleti", "Senaki-Kolkhi", "Batumi", "Kutaisi-Kopitnari", "Tbilisi-Lochini",
]
CAUCASUS_RED_AIRPORTS = [
    "Anapa-Vityazevo", "Krasnodar-Center", "Krasnodar-Pashkovsky", "Sochi-Adler",
    "Maykop-Khanskaya", "Gelendzhik", "Novorossiysk", "Krymsk", "Gudauta", "Sukhumi-Babushara",
]

ALL_CAUCASUS_AIRPORTS = CAUCASUS_BLUE_AIRPORTS + CAUCASUS_RED_AIRPORTS

TIME_OF_DAY = Literal["dawn", "day", "dusk", "night"]
WEATHER = Literal["clear", "fair", "poor", "storm"]
MISSION_TYPE = Literal["CAP", "STRIKE"]

# Every field below that maps to a concrete DCS asset is a real Literal enum
# (not a free string) so the LLM's structured-output schema enforces validity
# at generation time - the model literally cannot emit a value outside the
# whitelist. validate_whitelists() below is a defense-in-depth backstop for
# callers that build a MissionSpec by hand instead of via the LLM parser.
PlayerAircraft = Literal[*PLAYER_AIRCRAFT]
EnemyAirUnit = Literal[*ENEMY_AIR_UNITS]
StrikeTargetProfile = Literal[*STRIKE_TARGET_PROFILES.keys()]
BlueCountry = Literal[*BLUE_COUNTRIES]
RedCountry = Literal[*RED_COUNTRIES]
HomeAirport = Literal[*CAUCASUS_BLUE_AIRPORTS]
TargetAirport = Literal[*ALL_CAUCASUS_AIRPORTS]


class MissionSpec(BaseModel):
    title: str = Field(..., description="Short mission title")
    briefing: str = Field(..., description="1-3 sentence pilot briefing")

    mission_type: MISSION_TYPE

    player_country: BlueCountry = "USA"
    player_aircraft: PlayerAircraft
    player_aircraft_count: int = Field(1, ge=1, le=4)
    home_airport: HomeAirport = Field(..., description="Blue-friendly Caucasus airport name for the player flight")

    enemy_country: RedCountry = "Russia"
    target_airport: TargetAirport = Field(
        ..., description="Nearest Caucasus airport to the objective area; anchors where threats/targets spawn"
    )

    # CAP-specific
    enemy_air_unit: EnemyAirUnit | None = Field(None, description="Red CAP aircraft type")
    enemy_air_count: int = Field(2, ge=1, le=4)

    # STRIKE-specific
    strike_target_profile: StrikeTargetProfile | None = Field(
        None, description="Named ground target composition"
    )

    time_of_day: TIME_OF_DAY = "day"
    weather: WEATHER = "clear"

    def validate_whitelists(self) -> None:
        errors = []
        if self.mission_type == "CAP" and self.enemy_air_unit is None:
            errors.append("mission_type is CAP but enemy_air_unit was not set")
        if self.mission_type == "STRIKE" and self.strike_target_profile is None:
            errors.append("mission_type is STRIKE but strike_target_profile was not set")
        if errors:
            raise ValueError("MissionSpec validation failed:\n" + "\n".join(errors))
