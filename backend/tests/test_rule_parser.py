from app.rule_parser import parse_prompt_rule_based


def test_cap_prompt_extracts_aircraft_and_counts():
    spec = parse_prompt_rule_based(
        "Dawn CAP over Sochi-Adler with two F-16s against a pair of MiG-29s"
    )
    assert spec.mission_type == "CAP"
    assert spec.player_aircraft == "F_16C_50"
    assert spec.player_aircraft_count == 2
    assert spec.target_airport == "Sochi-Adler"
    assert spec.enemy_air_unit == "MiG_29S"
    assert spec.enemy_air_count == 2
    assert spec.time_of_day == "dawn"


def test_strike_prompt_extracts_target_profile():
    spec = parse_prompt_rule_based("Strike a convoy near Krasnodar with an A-10")
    assert spec.mission_type == "STRIKE"
    assert spec.player_aircraft == "A_10C_2"
    assert spec.target_airport == "Krasnodar-Center"
    assert spec.strike_target_profile == "convoy"


def test_sam_site_keyword_maps_to_sam_site_profile():
    spec = parse_prompt_rule_based("destroy a SAM site near Gelendzhik using a warthog")
    assert spec.mission_type == "STRIKE"
    assert spec.player_aircraft == "A_10C_2"
    assert spec.strike_target_profile == "sam_site"


def test_weather_and_time_keywords_detected():
    spec = parse_prompt_rule_based("intercept enemy fighters near Anapa at night in stormy weather")
    assert spec.time_of_day == "night"
    assert spec.weather == "storm"


def test_completely_vague_prompt_still_produces_valid_spec():
    spec = parse_prompt_rule_based("give me something to fly")
    spec.validate_whitelists()
    assert spec.player_aircraft == "F_16C_50"
    assert spec.mission_type == "CAP"


def test_never_raises_on_arbitrary_text():
    # Should always produce a valid spec, never throw, regardless of input.
    for prompt in ["asdf jkl;", "🚀🚀🚀", "a" * 500, "STRIKE STRIKE STRIKE"]:
        spec = parse_prompt_rule_based(prompt)
        spec.validate_whitelists()
