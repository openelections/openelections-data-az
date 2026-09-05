#!/usr/bin/env python3
"""Parse Mohave County's 2026 primary precinct results from the Clarity reports.

Source: ~/code/openelections-sources-az/2026/primary/Mohave AZ 2026 Primary
Precinct Results Report.pdf (456 pages). The report covers 48 Clarity units:
the county's 24 geographic precincts (MOHA_PCT1-24) plus a FED_MOHA_PCTn unit
beside each one holding the ballots of federal-only voters (registered without
proof of citizenship, they receive the federal races only). The FED units are
not separate precincts: their U.S. House rows and statistics are folded into
the parent precinct here, which is what makes every contest total and the
countywide statistics reconcile exactly with the official Summary Results
Report (Ballots Cast 44,664 = 44,652 geographic + 12 federal-only).

Each unit has a Statistics block (Registered Voters / Ballots Cast / Ballots
Cast - Blank with per-party and vote-method breakdowns: Election Day, Early,
Provisional) followed by contest blocks for the REP/DEM/GRN/LBT/NOL primaries
and the nonpartisan races of Bullhead City, Kingman, Lake Havasu City, and
Colorado City (the report's "Lake Havasau CIty" is a source typo). In each
contest block, Total Votes Cast = named candidates + Write-In Totals;
"Write-In:" rows are the attribution detail (skipped here, along with "Not
Assigned" and the Overvotes/Undervotes counts).

Writes 2026/counties/20260721__az__primary__mohave__precinct.csv, then
validates the output: per-contest candidate sums against "Total Votes Cast",
per-unit statistics against their party breakdowns, merged countywide
statistics and contest totals against the Summary Results Report, and named
statewide candidates against the statewide 2026/20260721__az__primary__county.csv.
"""

import csv
import os
import re
import sys
from collections import defaultdict

import pdfplumber

PDF_PATH = os.path.expanduser(
    '~/code/openelections-sources-az/2026/primary/'
    'Mohave AZ 2026 Primary Precinct Results Report.pdf'
)
SUMMARY_PATH = os.path.expanduser(
    '~/code/openelections-sources-az/2026/primary/'
    'Mohave AZ 2026 Primary Summary Results Report.pdf'
)
OUTPUT_PATH = '2026/counties/20260721__az__primary__mohave__precinct.csv'
COUNTY_FILE = '2026/20260721__az__primary__county.csv'
COUNTY = 'Mohave'
PRECINCT_COUNT = 24

# Countywide figures from the Summary Results Report (page 1). The 2026
# primary offers three vote methods: Election Day, Early, Provisional.
EXPECTED_RV_TOTAL = 149335
EXPECTED_RV_PARTY = {
    'Republican Party': 84028, 'Democratic Party': 17746, 'Green Party': 129,
    'Libertarian Party': 967, 'No Labels Party': 1447, 'Nonpartisan': 45018,
}
EXPECTED_BC = (44664, 9030, 35316, 318)  # total, election day, early, provisional
EXPECTED_BC_PARTY = {
    'Republican Party': (35454, 8137, 27040, 277),
    'Democratic Party': (7983, 720, 7232, 31),
    'Green Party': (22, 6, 16, 0),
    'Libertarian Party': (104, 19, 85, 0),
    'No Labels Party': (1006, 104, 894, 8),
    'Nonpartisan': (95, 44, 49, 2),
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
}

# Contest labels with the district (or justice-court precinct) embedded.
DISTRICTED_OFFICES = [
    (r'U\.S\. Representative in Congress Dist\. (\d+)', 'U.S. House'),
    (r'State Senator Dist\. (\d+)', 'State Senate'),
    (r'State Representative Dist\. (\d+)', 'State Representative'),
    (r'Judge of the Superior Court Div\. (\d+)', 'Judge of the Superior Court'),
    (r'Justice of the Peace (Bullhead|Cerbat|Kingman|Lake Havasu|North Canyon)',
     'Justice of the Peace'),
    (r'Constable (Bullhead|Cerbat|Kingman|Lake Havasu|North Canyon)', 'Constable'),
]

# Printed jurisdiction names needing cleanup (source typos / missing prefix).
JURISDICTION_FIXES = {
    'Lake Havasau CIty': 'City of Lake Havasu City',
    'Colorado City': 'Town of Colorado City',
}

SKIP_PREFIXES = (
    'Preinct Results Report',   # sic: typo in the source page header
    'OFFICIAL RESULTS', 'Primary Election', 'CANVASS', 'July',
    'Statistics', 'TOTAL', 'Day', 'Vote For', 'Precinct Summary', 'Voter Turnout',
)

FOUR_NUMS = re.compile(
    r'^(?P<label>.+?)\s+(?P<t>\d[\d,]*)\s+(?P<ed>\d[\d,]*)\s+(?P<ev>\d[\d,]*)'
    r'\s+(?P<pr>\d[\d,]*)$'
)
ONE_NUM = re.compile(r'^(?P<label>.+?)\s+(?P<n>\d[\d,]*)$')
PRECINCT = re.compile(r'^(?:FED_)?MOHA_PCT\d+$')
CONTEST = re.compile(r'^(REP|DEM|GRN|LBT|NOL)\s+(.+)$')
VOTE_FOR = re.compile(r'^Vote For \d+$')


def unit_key(unit):
    """Parent precinct of a Clarity unit (FED_MOHA_PCTn -> MOHA_PCTn)."""
    return unit[4:] if unit.startswith('FED_') else unit


def jurisdiction(raw):
    """Printed jurisdiction name -> district value, fixing source typos."""
    district = JURISDICTION_FIXES.get(raw, raw)
    if not district.startswith(('City of ', 'Town of ')):
        raise ValueError(f'Unknown jurisdiction: {raw!r}')
    return district


def normalize_office(label):
    """Map a printed contest label to (office, district)."""
    for pattern, office in DISTRICTED_OFFICES:
        m = re.fullmatch(pattern, label)
        if m:
            return office, m.group(1)
    if label in SIMPLE_OFFICES:
        return SIMPLE_OFFICES[label], ''
    m = re.fullmatch(r'Mayor (.+)', label)
    if m:
        return 'Mayor', jurisdiction(m.group(1))
    m = re.fullmatch(r'Council(?: Member)? (.+)', label.replace('-Unexp', ''))
    if m:
        district = jurisdiction(m.group(1).strip())
        if '-Unexp' in label:
            district += ' Unexpired Term'
        return 'Councilmember', district
    if label == 'Proposal submitted by the Kingman City Council.':
        return 'Proposal submitted by the Kingman City Council', 'City of Kingman'
    raise ValueError(f'Unknown contest label: {label!r}')


def flip_name(raw):
    """'Crane, Eli' -> 'Eli Crane' (spelled first-last like county.csv)."""
    if ',' in raw:
        last, first = raw.split(',', 1)
        return f'{first.strip()} {last.strip()}'
    return raw.strip()


def four_nums(m):
    """(total, election_day, early_voting, provisional) from a match."""
    return tuple(int(m.group(k).replace(',', '')) for k in ('t', 'ed', 'ev', 'pr'))


def add(nums, held):
    """Componentwise vote sum for merging FED rows into their parent."""
    return list(nums) if held is None else [a + b for a, b in zip(held, nums)]


def parse_precinct_report():
    """Parse all 48 units, folding FED rows into their parent precinct."""
    rows_by_precinct = defaultdict(dict)  # precinct -> {(o, d, p, cand): [t, ed, ev, pr]}
    totals = {}   # (precinct, office, district, party) -> [t, ed, ev, pr]
    stats = {}    # unit -> {'rv', 'rv_party', 'bc', 'blank', 'bc_party'}
    unparsed = []
    unit, contest = None, None

    with pdfplumber.open(PDF_PATH) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]

    for text in pages:
        lines = [raw.strip() for raw in text.split('\n')]
        for j, line in enumerate(lines):
            if not line or line.startswith(SKIP_PREFIXES):
                continue
            if PRECINCT.match(line):
                # The unit header repeats at the top of every page of its
                # block; start new state only when the label changes.
                if line != unit:
                    unit, contest = line, None
                    stats[unit] = {'rv': None, 'rv_party': {}, 'bc': None,
                                   'blank': None, 'bc_party': {}}
            elif line.startswith('Registered Voters - Total'):
                stats[unit]['rv'] = int(ONE_NUM.match(line).group('n').replace(',', ''))
            elif line.startswith('Registered Voters - '):
                m = ONE_NUM.match(line)
                party = m.group('label').removeprefix('Registered Voters - ')
                stats[unit]['rv_party'][party] = int(m.group('n').replace(',', ''))
            elif line.startswith('Ballots Cast - Total'):
                stats[unit]['bc'] = four_nums(FOUR_NUMS.match(line))
            elif line.startswith('Ballots Cast - Blank'):
                stats[unit]['blank'] = four_nums(FOUR_NUMS.match(line))
            elif line.startswith('Ballots Cast - '):
                m = FOUR_NUMS.match(line)
                party = m.group('label').removeprefix('Ballots Cast - ')
                stats[unit]['bc_party'][party] = four_nums(m)
            elif j + 1 < len(lines) and VOTE_FOR.match(lines[j + 1]):
                m = CONTEST.match(line)
                if m:
                    contest = (*normalize_office(m.group(2).strip()), PARTIES[m.group(1)])
                else:
                    contest = (*normalize_office(line), '')
            elif contest:
                if line.startswith(('Write-In:', 'Not Assigned', 'Overvotes', 'Undervotes')):
                    # Attributed write-in detail, unattributed remainder, and
                    # over/undervote counts; the Write-In Totals row already
                    # covers the first two.
                    continue
                if line.startswith('Total Votes Cast'):
                    key = (unit_key(unit), *contest)
                    totals[key] = add(four_nums(FOUR_NUMS.match(line)), totals.get(key))
                    continue
                m = FOUR_NUMS.match(line)
                if not m:
                    unparsed.append((unit, line))
                    continue
                candidate = 'Write-in' if line.startswith('Write-In Totals') else flip_name(
                    m.group('label'))
                precinct_rows = rows_by_precinct[unit_key(unit)]
                key = (*contest, candidate)
                precinct_rows[key] = add(four_nums(m), precinct_rows.get(key))
            else:
                unparsed.append((unit, line))
    return rows_by_precinct, totals, stats, unparsed


def merge_stats(stats):
    """Fold each FED unit's statistics into its parent precinct."""
    merged = {}
    for unit, s in stats.items():
        m = merged.setdefault(unit_key(unit), {
            'rv': 0, 'bc': [0, 0, 0, 0], 'blank': [0, 0, 0, 0],
            'rv_party': defaultdict(int), 'bc_party': {},
        })
        m['rv'] += s['rv'] or 0
        m['bc'] = add(s['bc'] or (0, 0, 0, 0), m['bc'])
        m['blank'] = add(s['blank'] or (0, 0, 0, 0), m['blank'])
        for party, n in s['rv_party'].items():
            m['rv_party'][party] += n
        for party, nums in s['bc_party'].items():
            m['bc_party'][party] = add(nums, m['bc_party'].get(party))
    return merged


def build_rows(rows_by_precinct, merged):
    """Summary rows plus contest rows, one precinct at a time in numeric order."""
    rows = []
    for precinct in sorted(rows_by_precinct, key=lambda p: int(re.search(r'\d+', p).group())):
        s = merged[precinct]
        rows.append([COUNTY, precinct, 'Registered Voters', '', '', '', s['rv'], '', '', ''])
        rows.append([COUNTY, precinct, 'Ballots Cast', '', '', '', *s['bc']])
        rows.append([COUNTY, precinct, 'Ballots Cast - Blank', '', '', '', *s['blank']])
        for (office, district, party, candidate), nums in rows_by_precinct[precinct].items():
            rows.append([COUNTY, precinct, office, district, party, candidate, *nums])
    return rows


def summary_contest_totals():
    """Countywide Total Votes Cast per contest from the Summary Results Report."""
    expected = {}
    label = None
    with pdfplumber.open(SUMMARY_PATH) as pdf:
        for page in pdf.pages:
            lines = [raw.strip() for raw in (page.extract_text() or '').split('\n')]
            for j, line in enumerate(lines):
                if not line or line.startswith(SKIP_PREFIXES):
                    continue
                if j + 1 < len(lines) and VOTE_FOR.match(lines[j + 1]):
                    m = CONTEST.match(line)
                    label = ((*normalize_office(m.group(2).strip()), PARTIES[m.group(1)])
                             if m else (*normalize_office(line), ''))
                elif label and line.startswith('Total Votes Cast'):
                    votes = int(re.match(r'^Total Votes Cast\s+(\d[\d,]*)', line)
                                .group(1).replace(',', ''))
                    expected[label] = expected.get(label, 0) + votes
                    label = None
    return expected


def validate(rows_by_precinct, totals, stats, merged, unparsed):
    errors = []
    if unparsed:
        errors.append(f'{len(unparsed)} unparsed lines, e.g. {unparsed[:5]}')

    # Per-unit statistics: party breakdowns must sum to the totals, and every
    # vote-method breakdown must sum to its vote count.
    for unit, s in stats.items():
        if sum(s['rv_party'].values()) != s['rv']:
            errors.append(f'{unit}: party registration sum != {s["rv"]}')
        if sum(n[0] for n in s['bc_party'].values()) != s['bc'][0]:
            errors.append(f'{unit}: party ballots-cast sum != {s["bc"][0]}')
        for row in [s['bc'], s['blank'], *s['bc_party'].values()]:
            if sum(row[1:]) != row[0]:
                errors.append(f'{unit}: method breakdown {row[1:]} != votes {row[0]}')

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

    # Contest blocks: DEM/REP each cover 24 precincts x (10 offices + 7 judge
    # divisions + JP + Constable + U.S. House) = 480; GRN/LBT/NOL each 24 x
    # (9 offices + U.S. House) = 240 (those primaries have no Clerk, Judge,
    # JP, or Constable contests); plus 22 city/town blocks.
    expected_blocks = 2 * 480 + 3 * 240 + 22
    if len(totals) != expected_blocks:
        errors.append(f'expected {expected_blocks} contest blocks, found {len(totals)}')
    if sum(1 for k in totals if k[3] == '') != 22:
        errors.append('expected exactly 22 nonpartisan (city/town) contest blocks')

    # Merged countywide statistics must match the Summary Results Report.
    if sum(m['rv'] for m in merged.values()) != EXPECTED_RV_TOTAL:
        errors.append(f'Registered Voters countywide != {EXPECTED_RV_TOTAL}')
    bc_total = [0, 0, 0, 0]
    rv_party = defaultdict(int)
    bc_party = defaultdict(lambda: [0, 0, 0, 0])
    for m in merged.values():
        bc_total = [a + b for a, b in zip(bc_total, m['bc'])]
        for party, n in m['rv_party'].items():
            rv_party[party] += n
        for party, nums in m['bc_party'].items():
            bc_party[party] = add(nums, bc_party[party])
    if tuple(bc_total) != EXPECTED_BC:
        errors.append(f'Ballots Cast countywide {tuple(bc_total)} != {EXPECTED_BC}')
    for party, n in EXPECTED_RV_PARTY.items():
        if rv_party[party] != n:
            errors.append(f'RV {party} {rv_party[party]} != {n}')
    for party, n in EXPECTED_BC_PARTY.items():
        if tuple(bc_party[party]) != tuple(n):
            errors.append(f'BC {party} {tuple(bc_party[party])} != {tuple(n)}')

    # Contest totals must match the canvass Summary Results Report.
    for key, votes in summary_contest_totals().items():
        got = 0
        for contest_rows in rows_by_precinct.values():
            for (office, district, party, _candidate), nums in contest_rows.items():
                if (office, district, party) == key:
                    got += nums[0]
        if got != votes:
            errors.append(f'{key}: precinct total {got} != summary report {votes}')

    # Named candidates must match the statewide county file. county.csv
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
    rows_by_precinct, totals, stats, unparsed = parse_precinct_report()
    merged = merge_stats(stats)
    rows = build_rows(rows_by_precinct, merged)
    errors = validate(rows_by_precinct, totals, stats, merged, unparsed)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate',
                         'votes', 'election_day', 'early_voting', 'provisional'])
        writer.writerows(rows)

    print(f'wrote {len(rows)} rows for {len(rows_by_precinct)} precincts to {OUTPUT_PATH}')
    if errors:
        for e in errors:
            print(f'VALIDATION ERROR: {e}', file=sys.stderr)
        sys.exit(1)
    print('all validations passed')


if __name__ == '__main__':
    main()