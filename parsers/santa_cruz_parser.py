#!/usr/bin/env python3
"""Parse Santa Cruz County's 2026 primary precinct results from the Statement
of Votes Cast.

Source: ~/code/openelections-sources-az/2026/primary/Santa Cruz AZ 2026 Primary
Statement of Votes Cast by Precinct.pdf (429 pages). The report covers 26
Clarity units over the county's 24 precincts: Coronado 5 and Patagonia 14 are
each split into two units by ballot style (e.g. "Coronado 5 05.1" and
"Coronado 5 05.2, 05.3, 05.4, 05.5"), which are merged into their precinct
here, matching the precinct labels used by the county's 2020-2022 files.

Each unit has a Statistics block (Registered Voters / Ballots Cast / Ballots
Cast - Blank with per-party and vote-method breakdowns: Election Day, Early,
Provisional) followed by contest blocks for the REP/DEM/GRN/LBT/NOL primaries,
the county offices, and the nonpartisan City of Nogales and Town of Patagonia
races plus Propositions 415 and 416. Unlike the other counties' reports,
candidate rows carry a vote-share column ("GRIJALVA, ADELITA 111 99.11% 16 95
0") and names are printed in all caps; they are flipped to first-last and
title-cased here. In each contest block, Total Votes Cast = named candidates +
Write-In Totals; "Write-In:" rows are the attribution detail (skipped here,
along with "Not Assigned" and the Overvotes/Undervotes counts).

Writes 2026/counties/20260721__az__primary__santa_cruz__precinct.csv, then
validates the output: per-contest candidate sums against "Total Votes Cast",
per-unit statistics against their party breakdowns, countywide statistics and
contest totals against the official Summary Report, and named state/federal
candidates against the statewide 2026/20260721__az__primary__county.csv.
"""

import csv
import os
import re
import sys
from collections import defaultdict

import pdfplumber

PDF_PATH = os.path.expanduser(
    '~/code/openelections-sources-az/2026/primary/'
    'Santa Cruz AZ 2026 Primary Statement of Votes Cast by Precinct.pdf'
)
SUMMARY_PATH = os.path.expanduser(
    '~/code/openelections-sources-az/2026/primary/'
    'Santa Cruz AZ 2026 Primary Summary Report.pdf'
)
OUTPUT_PATH = '2026/counties/20260721__az__primary__santa_cruz__precinct.csv'
COUNTY_FILE = '2026/20260721__az__primary__county.csv'
COUNTY = 'Santa Cruz'

# Countywide figures from the official Summary Report (page 1). The 2026
# primary offers three vote methods: Election Day, Early, Provisional.
EXPECTED_RV_TOTAL = 32699
EXPECTED_RV_PARTY = {
    'Democratic': 13629, 'Republican': 6071, 'Libertarian': 159,
    'Green': 23, 'No Labels': 232, 'Nonpartisan': 12585,
}
EXPECTED_BC = (7473, 1367, 6099, 7)  # total, election day, early, provisional
EXPECTED_BC_PARTY = {
    'Democratic': (5552, 798, 4749, 5),
    'Republican': (1811, 527, 1283, 1),
    'Libertarian': (13, 2, 11, 0),
    'Green': (2, 1, 1, 0),
    'No Labels': (69, 19, 49, 1),
    'Nonpartisan': (26, 20, 6, 0),
}

# Precinct labels match the county's 2020-2022 precinct files (precinct name
# plus number; ballot-style suffixes dropped, the two split units merged).
EXPECTED_PRECINCTS = {
    'Nogales 1', 'Nogales 2', 'Nogales 3', 'Nogales 4', 'Coronado 5', 'Elgin 6',
    'Rio Rico 7', 'Nogales 8', 'Nogales 9', 'Nogales 10', 'Tubac 11', 'Nogales 12',
    'Santa Cruz 13', 'Patagonia 14', 'Sonoita 15', 'Nogales 16', 'Calabasas 17',
    'Nogales 18', 'Baca 19', 'Nogales 20', 'Peck Canyon 21', 'Potrero 22',
    'Mountain 23', 'Lake Patagonia 24',
}

PARTIES = {'REP': 'REP', 'DEM': 'DEM', 'GRN': 'GRN', 'LBT': 'LBT', 'NOL': 'NOL'}

SIMPLE_OFFICES = {
    'Governor': 'Governor',
    'Secretary of State': 'Secretary of State',
    'State Treasurer': 'State Treasurer',
    'Attorney General': 'Attorney General',
    'Superintendent of Public Instruction': 'Superintendent of Public Instruction',
    'State Mine Inspector': 'State Mine Inspector',
    'Corporation Commissioner': 'Corporation Commissioner',
    'Clerk of the Superior Court': 'Clerk of the Superior Court',
    'Judge of the Superior Court': 'Judge of the Superior Court',
    'Justice of the Peace': 'Justice of the Peace',
    'Constable': 'Constable',
    'County School Superintendent': 'County School Superintendent',
}

# Contest labels with the district embedded in the printed name.
DISTRICTED_OFFICES = [
    (r'U\.S\. Representative in Congress Dist\. (\d+)', 'U.S. House'),
    (r'State Senator Dist\. (\d+)', 'State Senate'),
    (r'State Representative Dist\. (\d+)', 'State Representative'),
    (r'Judge of the Superior Court Div\. (\d+)', 'Judge of the Superior Court'),
]

SKIP_PREFIXES = (
    'Statement of Votes Cast', 'OFFICIAL RESULTS', 'Primary Election', 'July',
    'Statistics', 'TOTAL', 'Day', 'Vote For', 'Voter Turnout',
    'Election Day Precincts', 'Precincts',
)

# Candidate / Write-In Totals / Total Votes Cast rows: label + total + share
# + three vote-method counts. Overvotes/Undervotes carry no share column.
PCT_NUMS = re.compile(
    r'^(?P<label>.+?)\s+(?P<t>\d[\d,]*)\s+(?P<pct>\d[\d.]*)%\s+'
    r'(?P<ed>\d[\d,]*)\s+(?P<ev>\d[\d,]*)\s+(?P<pr>\d[\d,]*)$'
)
FOUR_NUMS = re.compile(
    r'^(?P<label>.+?)\s+(?P<t>\d[\d,]*)\s+(?P<ed>\d[\d,]*)\s+(?P<ev>\d[\d,]*)'
    r'\s+(?P<pr>\d[\d,]*)$'
)
ONE_NUM = re.compile(r'^(?P<label>.+?)\s+(?P<n>\d[\d,]*)$')
# Unit header: precinct name + number, then the ballot style list.
PRECINCT = re.compile(r'^(?P<name>[A-Za-z ]+?)\s+(?P<num>\d{1,2})\s+(?P<styles>\d{2}\.\d[\d.,\s]*)$')
CONTEST = re.compile(r'^(REP|DEM|GRN|LBT|NOL)\s+(.+)$')
VOTE_FOR = re.compile(r'^Vote For \d+$')


def normalize_office(label):
    """Map a printed contest label to (office, district)."""
    for pattern, office in DISTRICTED_OFFICES:
        m = re.fullmatch(pattern, label)
        if m:
            return office, m.group(1)
    if label in SIMPLE_OFFICES:
        return SIMPLE_OFFICES[label], ''
    m = re.fullmatch(r'(Mayor|Council Member) - (City|Town) of (.+)', label)
    if m:
        return 'Mayor' if m.group(1) == 'Mayor' else 'Councilmember', \
            f'{m.group(2)} of {m.group(3)}'
    m = re.fullmatch(r'PROPOSITION (\d+) - ((?:City|Town) of .+)', label)
    if m:
        return f'Proposition {m.group(1)}', m.group(2)
    raise ValueError(f'Unknown contest label: {label!r}')


def flip_name(raw):
    """'GRIJALVA, ADELITA' -> 'Adelita Grijalva' (county.csv spells first-last)."""
    if ',' in raw:
        last, first = raw.split(',', 1)
        return f'{first.strip()} {last.strip()}'.title()
    return raw  # e.g. proposition choices YES / NO, printed as-is in county files


def pct_nums(m):
    """(total, election_day, early_voting, provisional) from a match."""
    return tuple(int(m.group(k).replace(',', '')) for k in ('t', 'ed', 'ev', 'pr'))


def add(nums, held):
    """Componentwise vote sum for merging ballot-style units of a precinct."""
    return list(nums) if held is None else [a + b for a, b in zip(held, nums)]


def parse_precinct_report():
    """Parse all 26 ballot-style units, merging them into their 24 precincts."""
    rows_by_precinct = defaultdict(dict)  # precinct -> {(o, d, p, cand): [t, ed, ev, pr]}
    unit_totals = {}   # (unit, office, district, party) -> [t, ed, ev, pr]
    totals = {}        # (precinct, office, district, party) -> [t, ed, ev, pr]
    stats = {}         # precinct -> {'rv', 'rv_party', 'bc', 'blank', 'bc_party'}
    unparsed = []
    unit, precinct, contest = None, None, None
    wrap = False  # inside a "Write-In:" row whose long name wraps across lines

    with pdfplumber.open(PDF_PATH) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]

    for text in pages:
        lines = [raw.strip() for raw in text.split('\n')]
        for j, line in enumerate(lines):
            if not line or line.startswith(SKIP_PREFIXES):
                continue
            if wrap:
                # Continuation lines of a wrapped "Write-In:" row (e.g.
                # "POUNDS IV, WILLIAM" / "0 0 0 0" / "\"REX\" JOSUÉ"). Resume
                # at the first line that is a recognizable row of its own.
                if (line.startswith(('Write-In:', 'Not Assigned', 'Total Votes Cast',
                                     'Overvotes', 'Undervotes', 'TOTAL'))
                        or PRECINCT.match(line) or PCT_NUMS.match(line)
                        or VOTE_FOR.match(line)):
                    wrap = False
                else:
                    continue
            m = PRECINCT.match(line)
            if m:
                # The unit header repeats at the top of every page of its
                # block; start new state only when the label changes.
                if line != unit:
                    unit, contest = line, None
                    precinct = f'{m.group("name").strip()} {m.group("num")}'
                    stats.setdefault(precinct, {
                        'rv': 0, 'rv_party': defaultdict(int),
                        'bc': [0, 0, 0, 0], 'blank': [0, 0, 0, 0],
                        'bc_party': {},
                    })
                continue
            if precinct is None:
                unparsed.append((unit, line))
                continue
            if line.startswith('Registered Voters - Total'):
                stats[precinct]['rv'] += int(ONE_NUM.match(line).group('n').replace(',', ''))
            elif line.startswith('Registered Voters - '):
                mm = ONE_NUM.match(line)
                party = mm.group('label').removeprefix('Registered Voters - ')
                stats[precinct]['rv_party'][party] += int(mm.group('n').replace(',', ''))
            elif line.startswith('Ballots Cast - Total'):
                stats[precinct]['bc'] = add(pct_nums(FOUR_NUMS.match(line)), stats[precinct]['bc'])
            elif line.startswith('Ballots Cast - Blank'):
                stats[precinct]['blank'] = add(pct_nums(FOUR_NUMS.match(line)), stats[precinct]['blank'])
            elif line.startswith('Ballots Cast - '):
                mm = FOUR_NUMS.match(line)
                party = mm.group('label').removeprefix('Ballots Cast - ')
                stats[precinct]['bc_party'][party] = add(
                    pct_nums(mm), stats[precinct]['bc_party'].get(party))
            elif j + 1 < len(lines) and VOTE_FOR.match(lines[j + 1]):
                cm = CONTEST.match(line)
                if cm:
                    contest = (*normalize_office(cm.group(2).strip()), PARTIES[cm.group(1)])
                else:
                    contest = (*normalize_office(line), '')
            elif contest:
                if line.startswith(('Write-In:', 'Not Assigned', 'Overvotes', 'Undervotes')):
                    # Attributed write-in detail, unattributed remainder, and
                    # over/undervote counts; the Write-In Totals row already
                    # covers the first two. A "Write-In:" line without any
                    # numbers is the first piece of a wrapped row.
                    wrap = (line.startswith('Write-In:')
                            and not (PCT_NUMS.match(line) or FOUR_NUMS.match(line)))
                    continue
                if line.startswith('Total Votes Cast'):
                    # Zero-total blocks omit the vote-share column.
                    m2 = PCT_NUMS.match(line) or FOUR_NUMS.match(line)
                    key = (unit, *contest)
                    unit_totals[key] = add(pct_nums(m2), unit_totals.get(key))
                    pkey = (precinct, *contest)
                    totals[pkey] = add(unit_totals[key], totals.get(pkey))
                    continue
                m2 = PCT_NUMS.match(line) or FOUR_NUMS.match(line)
                if not m2:
                    unparsed.append((unit, line))
                    continue
                candidate = 'Write-in' if line.startswith('Write-In Totals') else flip_name(
                    m2.group('label'))  # zero rows may omit the vote-share column
                precinct_rows = rows_by_precinct[precinct]
                key = (*contest, candidate)
                precinct_rows[key] = add(pct_nums(m2), precinct_rows.get(key))
            else:
                unparsed.append((unit, line))
    return rows_by_precinct, totals, unit_totals, stats, unparsed


def build_rows(rows_by_precinct, stats):
    """Summary rows plus contest rows, one precinct at a time in name order."""
    rows = []
    for precinct in sorted(rows_by_precinct, key=lambda p: (int(re.search(r'\d+', p).group()))):
        s = stats[precinct]
        rows.append([COUNTY, precinct, 'Registered Voters', '', '', '', s['rv'], '', '', ''])
        rows.append([COUNTY, precinct, 'Ballots Cast', '', '', '', *s['bc']])
        rows.append([COUNTY, precinct, 'Ballots Cast - Blank', '', '', '', *s['blank']])
        for (office, district, party, candidate), nums in rows_by_precinct[precinct].items():
            rows.append([COUNTY, precinct, office, district, party, candidate, *nums])
    return rows


def summary_contest_totals():
    """Countywide Total Votes Cast per contest from the official Summary Report."""
    expected = {}
    label = None
    with pdfplumber.open(SUMMARY_PATH) as pdf:
        for page in pdf.pages:
            lines = [raw.strip() for raw in (page.extract_text() or '').split('\n')]
            for j, line in enumerate(lines):
                if not line or line.startswith(SKIP_PREFIXES):
                    continue
                if j + 1 < len(lines) and VOTE_FOR.match(lines[j + 1]):
                    cm = CONTEST.match(line)
                    label = ((*normalize_office(cm.group(2).strip()), PARTIES[cm.group(1)])
                             if cm else (*normalize_office(line), ''))
                elif label and line.startswith('Total Votes Cast'):
                    # Zero-total blocks omit the vote-share column.
                    votes = int((PCT_NUMS.match(line) or FOUR_NUMS.match(line))
                                .group('t').replace(',', ''))
                    expected[label] = expected.get(label, 0) + votes
                    label = None
    return expected


def validate(rows_by_precinct, totals, unit_totals, stats, unparsed):
    errors = []
    if unparsed:
        errors.append(f'{len(unparsed)} unparsed lines, e.g. {unparsed[:5]}')

    # 26 units: DEM/REP each cover all 26 x 15 contest types = 390 blocks;
    # GRN/LBT/NOL each 26 x 10 = 260 (those primaries have no Clerk, Judge,
    # Justice of the Peace, Constable, or County School Superintendent
    # contests); plus 39 city/town blocks (Nogales races x 12 units,
    # Patagonia races x 1).
    expected_blocks = 2 * 390 + 3 * 260 + 39
    if len(unit_totals) != expected_blocks:
        errors.append(f'expected {expected_blocks} contest blocks, found {len(unit_totals)}')

    # Statistics: party breakdowns must sum to the totals, and every
    # vote-method breakdown must sum to its vote count.
    for precinct, s in stats.items():
        if sum(s['rv_party'].values()) != s['rv']:
            errors.append(f'{precinct}: party registration sum != {s["rv"]}')
        if sum(n[0] for n in s['bc_party'].values()) != s['bc'][0]:
            errors.append(f'{precinct}: party ballots-cast sum != {s["bc"][0]}')
        for row in [s['bc'], s['blank'], *s['bc_party'].values()]:
            if sum(row[1:]) != row[0]:
                errors.append(f'{precinct}: method breakdown {row[1:]} != votes {row[0]}')
    if set(stats) != EXPECTED_PRECINCTS:
        errors.append(f'precincts mismatch: {set(stats) ^ EXPECTED_PRECINCTS}')

    # Per contest block: candidates + Write-in must equal Total Votes Cast.
    for precinct, contest_rows in rows_by_precinct.items():
        summed = {}
        for (office, district, party, _candidate), nums in contest_rows.items():
            key = (office, district, party)
            summed[key] = add(nums, summed.get(key))
        for key, nums in summed.items():
            expected = totals.get((precinct, *key))
            if expected is None:
                errors.append(f'{precinct} {key}: contest rows without a Total Votes Cast')
            elif nums != expected:
                errors.append(f'{precinct} {key}: candidates+write-in {nums} != '
                              f'Total Votes Cast {expected}')
        exp_keys = {k[1:] for k in totals if k[0] == precinct}
        if set(summed) != exp_keys:
            errors.append(f'{precinct}: contest keys {set(summed) ^ exp_keys} unmatched')

    # Countywide statistics must match the official Summary Report.
    if sum(s['rv'] for s in stats.values()) != EXPECTED_RV_TOTAL:
        errors.append(f'Registered Voters countywide != {EXPECTED_RV_TOTAL}')
    bc_total = [0, 0, 0, 0]
    rv_party = defaultdict(int)
    bc_party = defaultdict(lambda: [0, 0, 0, 0])
    for s in stats.values():
        bc_total = [a + b for a, b in zip(bc_total, s['bc'])]
        for party, n in s['rv_party'].items():
            rv_party[party] += n
        for party, nums in s['bc_party'].items():
            bc_party[party] = add(nums, bc_party[party])
    if tuple(bc_total) != EXPECTED_BC:
        errors.append(f'Ballots Cast countywide {tuple(bc_total)} != {EXPECTED_BC}')
    for party, n in EXPECTED_RV_PARTY.items():
        if rv_party[party] != n:
            errors.append(f'RV {party} {rv_party[party]} != {n}')
    for party, n in EXPECTED_BC_PARTY.items():
        if tuple(bc_party[party]) != tuple(n):
            errors.append(f'BC {party} {tuple(bc_party[party])} != {tuple(n)}')

    # Contest totals must match the official Summary Report.
    for key, votes in summary_contest_totals().items():
        got = 0
        for contest_rows in rows_by_precinct.values():
            for (office, district, party, _candidate), nums in contest_rows.items():
                if (office, district, party) == key:
                    got += nums[0]
        if got != votes:
            errors.append(f'{key}: precinct total {got} != summary report {votes}')

    # Named state/federal candidates must match the statewide county file
    # (county.csv covers no county or municipal offices for Santa Cruz). It
    # carries no district for these offices, so match on
    # office/party/candidate. Rows it flags as write-ins live only in
    # "Write-In:" detail rows here, so they are exempt from the vote
    # comparison.
    candidates = defaultdict(int)
    for contest_rows in rows_by_precinct.values():
        for (office, _district, party, candidate), nums in contest_rows.items():
            if candidate != 'Write-in':
                candidates[(office, party, candidate)] += nums[0]
    with open(COUNTY_FILE, newline='') as f:
        for rec in csv.DictReader(f):
            if rec['county'] != COUNTY or not rec['candidate'] or rec['write-in'] == 'True':
                continue
            key = (rec['office'], rec['party'], rec['candidate'])
            if candidates.get(key) != int(rec['votes']):
                errors.append(f'county.csv candidate not matched: '
                              f'{rec["candidate"]} {candidates.get(key)} != {rec["votes"]}')

    return errors


def main():
    rows_by_precinct, totals, unit_totals, stats, unparsed = parse_precinct_report()
    rows = build_rows(rows_by_precinct, stats)
    errors = validate(rows_by_precinct, totals, unit_totals, stats, unparsed)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate',
                         'votes', 'election_day', 'early_voting', 'provisional'])
        writer.writerows(rows)

    print(f'wrote {len(rows)} rows for {len(stats)} precincts to {OUTPUT_PATH}')
    if errors:
        for e in errors:
            print(f'VALIDATION ERROR: {e}', file=sys.stderr)
        sys.exit(1)
    print('all validations passed')


if __name__ == '__main__':
    main()