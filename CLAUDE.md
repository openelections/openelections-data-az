# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A data repository of pre-processed Arizona election results, published by OpenElections. The content is CSV files organized by year; the Python/Ruby scripts at the root are one-off scrapers/converters used to produce those files. There is no build, lint, or test suite in this repo itself.

## Data tests (CI)

PRs run the external test suite [openelections/openelections-data-tests](https://github.com/openelections/openelections-data-tests) (pinned `v2.2.0`) against **added** `*.csv` files, with one job per test: `file_format`, `duplicate_entries`, `missing_values`, `vote_breakdown_totals`.

To run locally, clone the data-tests repo alongside this one and run (from that repo):

```sh
python3 run_tests.py <test> --files <relative.csv ...> /path/to/openelections-data-az
```

- `<test>` is one of the four test names; `--files` restricts to specific files (paths relative to the data repo root, as reported by CI). Omit `--files` to test the whole repo.
- `vote_breakdown_totals` flags rows where the sum of vote-method breakdown columns exceeds `votes`; when headers match known schemas it requires equality.

Most recent work in this repo has been driving out these four test failures county file by county file (see git log; branches are named `claude/fix-*`, `claude/recover-*`).

## File naming and layout

- Files are named `<YYYYMMDD>__az__<election>__<county>__<level>.csv`, e.g. `20201103__az__general__apache__precinct.csv`. Election segment is `general`, `primary`, or `special__primary`/`special__general`; `__county__` or `__precinct__` denotes level.
- Older years (2000–2014): election files sit directly in the year directory (e.g. `2008/20081104__az__general.csv`), named without a county when they are statewide.
- 2016–2022: year directory contains a `counties/` subdirectory of per-county precinct files, plus (sometimes) a consolidated statewide `…__precinct.csv`.
- 2024 uses `General/` and `Primary/` subdirectories instead of `counties/`.
- County names in filenames are lowercase with underscores (`la_paz`).

## CSV schema conventions

- Standard columns: `county, precinct, office, district, party, candidate, votes`, optionally followed by vote-method breakdown columns (`election_day`, `early_voting`, `provisional`, and sometimes `late_early_voting`). Column order varies between county files.
- Non-candidate summary rows appear in the `office` column: `Registered Voters`, `Ballots Cast`, `Ballots Cast - Blank` (with breakdown columns zeroed out on `Registered Voters` rows).

## Scripts

Root-level scripts are ad-hoc converters, each hardcoded to a specific election — edit the constants at the top when reusing:

- `statewide_generator.py` — merges the per-county precinct CSVs of a year's `counties/` dir into a single statewide `…__precinct.csv`. Uses `os.chdir`, so run it from the repo root after setting `year`/`election` at the top.
- `precinct_parser.py` — downloads per-county Clarity `Detail` reports and writes precinct CSVs; county-specific column mappings live in its `COUNTIES`/`HEADERS` dicts.
- `clarity_parser.py`, `parser.py` — older one-off parsers for Clarity XML and canvass text files.
- `maricopa_parser.rb` — Ruby parser for Maricopa County files.

## Environment

- Python 3.12+, managed with `uv` (`pyproject.toml`, `uv.lock`). Dependencies: `requests`, `natural-pdf`.
- Historical scripts reference `unicodecsv` (not in `pyproject.toml`); install it ad hoc if running those.