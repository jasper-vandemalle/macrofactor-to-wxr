# macrofactor-to-wxr

[![CI](https://github.com/jasper-vandemalle/macrofactor-to-wxr/actions/workflows/ci.yml/badge.svg)](https://github.com/jasper-vandemalle/macrofactor-to-wxr/actions/workflows/ci.yml)

Logs your [MacroFactor](https://macrofactorapp.com/) workouts in your [weightxreps](https://weightxreps.net/) journal.

I track my training in MacroFactor, but I like weightxreps for the journal and the stats. MacroFactor has no API, but it can export your data to Excel. `mf2wxr` reads a workout from that export and saves it to weightxreps through its OAuth API, the same way the weightxreps editor would if you'd typed it in.

```console
$ mf2wxr push
From MacroFactor-20250301181502.xlsx:

2025-03-01
@ 80.4 bw

Lower A

#Squat (Barbell)
100 x 5 x 3 @8
105 x 3 @9

#Romanian Deadlift (Barbell)
90 x 10, 9, 8

#Pull Up
BW+10 x 8, 7

#Dumbbell Farmer's Carry
32x40m x 2

Logged Lower A on 2025-03-01: 4 exercises, 11 sets.
```

## What it takes care of

- Warm-up sets are skipped.
- Supersets are merged back into one block per exercise.
- MacroFactor logs the combined load of two dumbbells (and both sides of a cable fly). Those are halved to the per-dumbbell weight; single-arm and offset exercises are left alone.
- For pull-ups, chin-ups and dips, the weight is logged as added to your bodyweight (`BW+10`).
- RIR becomes RPE (2 RIR is RPE 8).
- Carries are logged as weight over distance.
- The bodyweight for the day is your last weigh-in on or before the workout.
- Exercises match your existing weightxreps exercises by name, ignoring case. Ones you don't have yet are created. If your journal uses different names, add [aliases](#aliases).
- If the day already has a log, it stops. Saving replaces the whole day, so you have to ask for that with `--replace`.

## Install

Needs Python 3.12 or newer. With [uv](https://docs.astral.sh/uv/):

```sh
uv tool install git+https://github.com/jasper-vandemalle/macrofactor-to-wxr
```

## Setup

weightxreps lets you register your own apps, so `mf2wxr` signs in as an app you create:

1. On weightxreps, open **Settings** and scroll to **Developer API**. Add a service:

   ```yaml
   services:
     - id: "mf2wxr"
       name: "mf2wxr"
       url: "https://github.com/jasper-vandemalle/macrofactor-to-wxr"
       redirectUris:
         - "http://127.0.0.1:8765/callback"
   ```

2. Sign in. Your browser opens to approve access to your journal:

   ```sh
   mf2wxr login --client-id mf2wxr
   ```

   The tokens are stored in `~/.config/mf2wxr/token.json`, readable only by you, and refreshed when they expire.

To skip `--client-id` and the export path from then on, create `~/.config/mf2wxr/config.toml`:

```toml
client_id = "mf2wxr"
exports = "~/Downloads"  # where your MacroFactor exports end up
```

## Usage

Export your workouts from MacroFactor as `.xlsx`, then:

```sh
mf2wxr push --dry-run             # show what would be logged, save nothing
mf2wxr push                       # log the latest workout from the newest export
mf2wxr push path/to/export.xlsx   # or from a specific file
mf2wxr push --date 2025-03-01     # a specific day instead of the latest
mf2wxr push --replace             # overwrite a day that already has a log
```

Without a path, `push` takes the newest export with workouts in it from the `exports` directory, or the current directory.

`mf2wxr text` prints the workout as editor text instead. Add `--copy` to put it on the clipboard (install with `uv tool install 'mf2wxr[clipboard] @ git+https://github.com/jasper-vandemalle/macrofactor-to-wxr'`), if you'd rather paste it in yourself.

### Aliases

If your journal already has an exercise under another name, map it in `~/.config/mf2wxr/aliases.toml`:

```toml
"Squat (Barbell)" = "Back Squat"
"Pull Up" = "Weighted Pull-up"
```

## How the sign-in works

It's OAuth2 with PKCE, so there's no client secret. One quirk: the weightxreps consent page doesn't redirect the browser to the callback straight away. It first `fetch`es the authorize endpoint, follows the redirect to the callback cross-origin to read the code, and only then navigates there. So the local callback server answers CORS preflights from weightxreps and stays up for that second request.

## Development

```sh
uv sync
uv run pytest
uv run ruff check && uv run ruff format --check
```

The tests build their own MacroFactor exports, so no real data is needed.

---

Not affiliated with MacroFactor or weightxreps. MIT licensed.
