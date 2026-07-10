"""Local FastAPI backend for the DCS Mission Companion desktop app.

Runs on localhost only - the Electron main process spawns this and talks to
it over HTTP. Not designed to be exposed to the network.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .llm_parser import ParseError, parse_prompt
from .mission_builder import MissionBuildError, save_mission
from .mission_spec import (
    CAUCASUS_BLUE_AIRPORTS,
    CAUCASUS_RED_AIRPORTS,
    ENEMY_AIR_UNITS,
    PLAYER_AIRCRAFT,
    STRIKE_TARGET_PROFILES,
    MissionSpec,
)
from .rule_parser import parse_prompt_rule_based

app = FastAPI(title="DCS Mission Companion")


class GenerateRequest(BaseModel):
    prompt: str
    moose_lua_path: str | None = None
    save_path: str | None = None  # absolute path to write the .miz; temp file if omitted
    anthropic_api_key: str | None = None  # overrides ANTHROPIC_API_KEY env var for this call


class GenerateResponse(BaseModel):
    spec: MissionSpec
    saved_path: str
    parser_used: str  # "claude" or "rule_based"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/options")
def options() -> dict:
    return {
        "player_aircraft": PLAYER_AIRCRAFT,
        "enemy_air_units": ENEMY_AIR_UNITS,
        "strike_target_profiles": list(STRIKE_TARGET_PROFILES.keys()),
        "home_airports": CAUCASUS_BLUE_AIRPORTS,
        "target_airports": CAUCASUS_BLUE_AIRPORTS + CAUCASUS_RED_AIRPORTS,
    }


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    if not req.prompt.strip():
        raise HTTPException(400, "prompt must not be empty")

    api_key = req.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            spec = parse_prompt(req.prompt, client=anthropic.Anthropic(api_key=api_key))
            parser_used = "claude"
        except ParseError as e:
            raise HTTPException(422, str(e)) from e
    else:
        # No API key configured - fall back to the offline keyword-based
        # parser instead of failing outright. Less flexible with vague or
        # creative phrasing, but works with zero setup and no network calls.
        spec = parse_prompt_rule_based(req.prompt)
        parser_used = "rule_based"

    if req.save_path:
        out_path = req.save_path
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    else:
        out_path = str(Path(tempfile.gettempdir()) / f"{_safe_filename(spec.title)}.miz")

    try:
        save_mission(spec, out_path, moose_lua_path=req.moose_lua_path)
    except MissionBuildError as e:
        raise HTTPException(422, str(e)) from e

    return GenerateResponse(spec=spec, saved_path=out_path, parser_used=parser_used)


@app.get("/download")
def download(path: str) -> FileResponse:
    p = Path(path)
    if not p.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(str(p), filename=p.name, media_type="application/octet-stream")


def _safe_filename(title: str) -> str:
    keep = [c if c.isalnum() or c in (" ", "-", "_") else "_" for c in title]
    return "".join(keep).strip().replace(" ", "_")[:60] or "mission"
