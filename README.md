# DCS Mission Companion

A desktop app that turns a plain-English request ("dawn CAP over Sochi with
two F-16s against a pair of MiG-29s") into a ready-to-fly DCS World mission
file (`.miz`) — no interaction with the DCS Mission Editor required.

Claude parses your prompt into a structured mission spec (or, with no API key
configured, a built-in offline keyword parser does — see
[Prompt parsing](#prompt-parsing-claude-vs-offline) below), then
[pydcs](https://github.com/pydcs/dcs) builds a real DCS mission from it
(units, waypoints, loadouts, weather, triggers), and generated Lua backed by
[MOOSE](https://github.com/FlightControl-Master/MOOSE) gives the mission
runtime dynamism (regenerating threats, reinforcement, objective tracking)
instead of static one-shot unit placement.

**v1 scope:** Caucasus map, Blue coalition player, CAP (intercept) and STRIKE
missions. See [Roadmap](#roadmap) for what's next.

## How it works

There is no live API into the DCS Mission Editor — missions are just Lua
tables inside a zipped `.miz` file, and that's the real integration point
every serious DCS tool (this one included) uses.

```
 plain-English prompt
        |
        v
 Claude (structured outputs)  ->  MissionSpec (validated JSON)
        |
        v
 pydcs mission builder        ->  units, waypoints, loadouts, weather, triggers
        |
        v
 generated MOOSE Lua          ->  dynamic threats / reinforcement / objectives
        |
        v
      mission.miz  ->  drop into your DCS Missions folder and fly
```

- `backend/` — Python engine: FastAPI server, the Claude-based prompt parser,
  and the pydcs mission builder. This does all the actual work.
- `desktop/` — Electron shell around the backend: a prompt box, a settings
  panel (API key, MOOSE path, DCS folder), and a "generate" button.

## Setup

### 1. Backend

```sh
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

An [Anthropic API key](https://console.anthropic.com/) is optional — enter it
in the app's Settings panel once the desktop app is running (or set
`ANTHROPIC_API_KEY` as an environment variable before launching) for flexible,
free-form prompt parsing. Without one, the app automatically falls back to a
built-in offline parser — see [Prompt parsing](#prompt-parsing-claude-vs-offline).

Run the test suite (no API key required — the LLM call is mocked):

```sh
pytest
```

### 2. MOOSE (optional, enables dynamic mission logic)

Missions still work without this — you just lose the dynamic-threat layer
(regenerating CAP flights, QRF reinforcement, objective tracking) and fall
back to static unit placement.

1. Download the latest static `Moose.lua` from the
   [MOOSE releases page](https://github.com/FlightControl-Master/MOOSE/releases)
   (look for `Moose_Include_Static/Moose.lua` in the release assets).
2. Save it anywhere on disk, e.g.
   `%USERPROFILE%\Saved Games\DCS.openbeta\Scripts\MOOSE\Moose.lua`.
3. Point the app's Settings panel at that file. The generator embeds a copy
   of it into every mission it builds (exactly what the Mission Editor does
   when you manually add a "DO SCRIPT FILE" trigger action) - it never
   references the file by path at mission runtime.

### 3. Desktop app

```sh
cd desktop
npm install
npm start
```

`npm install` downloads the Electron binary from GitHub releases — if your
network blocks that, install on a machine that doesn't (this is unrelated to
the Python/pydcs/Claude parts, which have no such restriction).

On launch, the app spawns the Python backend from `backend/venv` and opens
its own window. In Settings you can:

- enter your Anthropic API key
- point at your local `Moose.lua` (optional, see above)
- point at (or auto-detect) your DCS Saved Games `Missions` folder, so
  generated missions save straight there instead of a temp folder

### 4. Fly it

Type a prompt, hit **Generate mission**, then open the `.miz` from your DCS
Missions folder (or use **Show file in folder**) in DCS World.

## Prompt parsing: Claude vs. offline

The app has two interchangeable ways to turn your prompt into a mission spec,
and picks automatically based on whether an API key is configured:

- **Claude (API key set):** genuinely understands free-form, creative
  phrasing ("something moody and dangerous over the coast at dusk"), infers
  intent, and writes a custom briefing.
- **Offline keyword parser (no API key):** zero cost, zero setup, no network
  calls - pure Python string/keyword matching (`backend/app/rule_parser.py`).
  It recognizes common aircraft nicknames (F-16/Viper, Hornet, Warthog,
  Mirage, Flanker, Fulcrum, etc.), mission-type words (CAP/intercept/patrol
  vs. strike/bomb/destroy), target-profile words (convoy/SAM site/depot),
  airport names, numbers ("two", "a pair of", "4x"), and time-of-day/weather
  words. It always produces a valid mission by falling back to sensible
  defaults for anything it can't confidently extract - but it won't
  understand indirect or unusually-phrased requests the way Claude does, so
  prompts work best when they mention things somewhat literally, e.g. *"CAP
  over Sochi with two F-16s against a pair of MiG-29s"* rather than *"give me
  something fun near the water."*

The app tells you which one was used after each generation (shown next to
the saved file path).

## Troubleshooting

**`KeyError: 'country_list'` crash on startup (Windows, Python 3.13+):**
`pydcs` scans your DCS installation's aircraft liveries on first import, and
its scanner uses an old `exec()`/`locals()` trick that breaks on Python 3.13
and newer (a real upstream `pydcs` bug, not specific to this app). Either:
- install Python 3.11 or 3.12 alongside your current version and rebuild the
  venv with it (`py -3.11 -m venv venv`), or
- patch it directly: in
  `backend/venv/Lib/site-packages/dcs/liveries_scanner.py`, replace
  ```python
  exec(f"country_list = {countries}")
  countries = set(filter(lambda x: x != "", locals()['country_list']))
  ```
  with
  ```python
  country_list = eval(countries)
  countries = set(filter(lambda x: x != "", country_list))
  ```

## What "dynamic" means in v1

- **CAP missions**: the red flight is placed late-activated and a generated
  MOOSE `SPAWN` script keeps regenerating it from the target airbase for the
  mission duration, instead of a single scripted patrol you can kill once and
  be done with.
- **STRIKE missions**: the ground target is placed live; a MOOSE scheduler
  polls it, launches a QRF reinforcement group once it takes losses, and
  announces mission-objective completion (sets a DCS flag) once it's wiped
  out.

Both layers sit on top of a fully valid static mission — if the dynamic Lua
were ever to no-op for any reason, the mission still loads and flies fine.

## Roadmap

- More theaters (Syria, Persian Gulf, Nevada)
- Red-side player missions
- More mission types (SEAD, escort, CSAR, transport)
- MOOSE `AI_A2A_DISPATCHER` / `AI_A2G_DISPATCHER` for genuinely emergent AI
  behavior instead of the current SPAWN/scheduler-based dynamism
- Richer ground-target compositions (proper SAM sites, IADS)
- Packaged desktop builds (no manual `venv`/`npm install` setup)
