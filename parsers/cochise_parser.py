#!/usr/bin/env python3
"""Parse Cochise County's 2026 primary precinct results from the Statement of
Votes Cast.

Source: ~/code/openelections-sources-az/2026/primary/Cochise AZ 2026 Primary
Statement of Votes Cast Precinct Summary.pdf (1,110 pages; ~20 pages per unit
over the county's 55 precincts). Each unit has a Statistics block (Registered
Voters / Ballots Cast / Ballots Cast - Blank with per-party and vote-method
breakdowns: Election Day, Early, Provisional) followed by contest blocks for
the REP/DEM/GRN/LBT/NOL primaries, the county offices (Clerk, Recorder, three
Superior Court divisions), and the nonpartisan city races of Benson, Bisbee,
Douglas, Tombstone and Willcox. Candidate rows carry a vote-share column
("Ciscomani, Juan 376 87.85% 96 280 0") and names are printed first-last, so
only the comma flip is needed. Zero-total rows omit the share column. In each
contest block, Total Votes Cast = named candidates + Write-In Totals;
"Write-In: Unofficial" rows are the unattributed write-in detail (skipped
here, along with "Not Assigned", the Overvotes/Undervotes counts, and the
per-contest "Contest Totals" row). Bisbee elects its council by ward
("Cnl. Mbr. WD III 2YR" is the ward's unexpired two-year seat); Douglas and
Tombstone wards print as "Council Mem W2".

Writes 2026/counties/20260721__az__primary__cochise__precinct.csv, then
validates the output: per-contest candidate sums against "Total Votes Cast",
per-unit statistics against their party breakdowns, countywide statistics and
contest totals against the Cumulative Official Final Report, and named
state/federal candidates against the statewide
2026/20260721__az__primary__county.csv.
"""

import csv
import os
import re
import sys
from collections import defaultdict

import pdfplumber

PDF_PATH = os.path.expanduser(
    '~/code/openelections-sources-az/2026/primary/'
    'Cochise AZ 2026 Primary Statement of Votes Cast Precinct Summary.pdf'
)
SUMMARY_PATH = os.path.expanduser(
    '~/code/openelections-sources-az/2026/primary/'
    'Cochise AZ 2026 Primary Cumulative Official Final Report.pdf'
)
OUTPUT_PATH = '2026/counties/20260721__az__primary__cochise__precinct.csv'
COUNTY_FILE = '2026/20260721__az__primary__county.csv'
COUNTY = 'Cochise'

# Countywide figures from the Cumulative Official Final Report (page 1). The
# 2026 primary offers three vote methods: Election Day, Early, Provisional.
EXPECTED_RV_TOTAL = 82413
EXPECTED_RV_PARTY = {
    'Republican': 33020, 'Democratic': 18372, 'Green': 102,
    'Libertarian': 684, 'No Labels': 946, 'Nonpartisan': 29289,
}
EXPECTED_BC = (23413, 4038, 19353, 22)  # total, election day, early, provisional
EXPECTED_BC_PARTY = {
    'Republican': (14112, 3337, 10756, 19),
    'Democratic': (8846, 612, 8231, 3),
    'Green': (26, 4, 22, 0),
    'Libertarian': (81, 17, 64, 0),
    'No Labels': (309, 39, 270, 0),
    'Nonpartisan': (39, 29, 10, 0),
}
EXPECTED_BC_BLANK = (17, 5, 12, 0)

# Precinct labels as printed (the county's 2022 file uses the same labels).
EXPECTED_PRECINCTS = {
    '01 BE BENSON', '02 BE J-SIX', '03 BE SAN PEDRO', '04 BI BISBEE',
    '05 BI DON LUIS', '06 BI WARREN', '07 BOWIE', '08 COCHISE STRONGHOLD',
    '09 DO CALVARY', '10 DO CARLSON', '11 DO CASTRO PARK', '12 DO GADSDEN',
    '13 DO SUNNYSIDE', '14 GREATER SAN PEDRO', '15 HEREFORD', '16 HUACHUCA',
    '17 MCNEAL', '18 NACO', '19 PALOMINAS', '20 PIRTLEVILLE', '21 POMERENE',
    '22 PORTAL', '23 SAN SIMON', '24 ST DAVID', '25 SUNIZONA',
    '26 SV AVENIDA DEL SOL', '27 SV BUFFALO SOLDIER', '28 SV BUSBY',
    '29 SV CARMELITA', '30 SV CLOUD', '31 SV COLLEGE', '32 SV COUNTRY CLUB',
    '33 SV ESTATES', '34 SV HOPI', '35 SV MOSON', '36 SV PUEBLO DEL SOL',
    '37 SV RAMSEY', '38 SV SNYDER', '39 SV SOLDIER CREEK',
    '40 SV TOWN & COUNTRY', '41 SV VILLAGE MEADOWS', '42 SV VISTA VILLAGE',
    '43 SV YAQUI', '44 TOMBSTONE', '45 WEBB', '46 WHETSTONE',
    '47 WI KANSAS SETTLEMENT', '48 WI STEWART', '49 WI WILLCOX', '50 DO GRAND',
    '51 BI SACRAMENTO', '52 THREE CANYONS', '53 GREENBUSH', '54 PARKER',
    '55 MONTEZUMA',
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
    'County Recorder': 'County Recorder',
}

# Contest labels with the district (or justice-court precinct) embedded.
DISTRICTED_OFFICES = [
    (r'U\.S\. Representative in Congress Dist\. (\d+)', 'U.S. House'),
    (r'State Senator Dist\. (\d+)', 'State Senate'),
    (r'State Representative Dist\. (\d+)', 'State Representative'),
    (r'Judge of the Superior Court Div\. (\d+)', 'Judge of the Superior Court'),
    (r'Justice of the Peace Prec\. (\d+)', 'Justice of the Peace'),
    (r'Constable Prec\. (\d+)', 'Constable'),
    (r'Precinct Committeemen Pct (\d+)', 'Precinct Committeeman'),
]

ROMAN = {'I': '1', 'II': '2', 'III': '3'}

# county.csv spellings that the report prints differently.
NAME_FIXES = {
    'Rosanna Gabaldon': 'Rosanna Gabaldón',
}

SKIP_PREFIXES = (
    'Primary Election', 'State of Arizona', 'July 21, 2026', 'Statistics',
    'TOTAL', 'Day', 'Vote For', 'Voter Turnout', 'Contest Totals',
    'Precinct Summary',
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
# Unit header: precinct number plus all-caps name (repeats at page tops).
PRECINCT = re.compile(r'^(?P<num>\d{1,3})\s+(?P<name>[A-Z][A-Z &.\-]+)$')
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
    m = re.fullmatch(r'City of (.+?) (.+)', label)  # city names are single words
    if m:
        city, race = m.groups()
        district = f'City of {city}'
        if race == 'Mayor':
            return 'Mayor', district
        if race == 'Council Member':  # at-large (Benson, Willcox)
            return 'Councilmember', district
        m2 = re.fullmatch(r'Cnl\. Mbr\. WD ([IVX]+)(?: (\d)YR)?', race)
        if m2:
            ward = ROMAN[m2.group(1)]
            if m2.group(2) == '2':  # the 2YR copy is the unexpired seat
                return 'Councilmember', f'{district} Ward {ward} Unexpired Term'
            return 'Councilmember', f'{district} Ward {ward}'
        m2 = re.fullmatch(r'Council Mem W(\d)', race)
        if m2:
            return 'Councilmember', f'{district} Ward {m2.group(1)}'
    raise ValueError(f'Unknown contest label: {label!r}')


def flip_name(raw):
    """'Ciscomani, Juan' -> 'Juan Ciscomani' (spelled first-last like county.csv)."""
    if ',' in raw:
        last, first = raw.split(',', 1)
        return f'{first.strip()} {last.strip()}'
    return raw.strip()


def pct_nums(m):
    """(total, election_day, early_voting, provisional) from a match."""
    return tuple(int(m.group(k).replace(',', '')) for k in ('t', 'ed', 'ev', 'pr'))


def add(nums, held):
    """Componentwise vote sum; keeps per-precinct state across page-top repeats."""
    return list(nums) if held is None else [a + b for a, b in zip(held, nums)]


def parse_precinct_report():
    """Parse the 55 precinct units of the Statement of Votes Cast."""
    rows_by_precinct = defaultdict(dict)  # precinct -> {(o, d, p, cand): [t, ed, ev, pr]}
    totals = {}   # (precinct, office, district, party) -> [t, ed, ev, pr]
    stats = {}    # precinct -> {'rv', 'rv_party', 'bc', 'blank', 'bc_party'}
    unparsed = []
    unit, contest = None, None
    wrap = False  # inside a "Write-In:" row whose long name wraps across lines

    with pdfplumber.open(PDF_PATH) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]

    for text in pages:
        lines = [raw.strip() for raw in text.split('\n')]
        for j, line in enumerate(lines):
            if not line or line.startswith(SKIP_PREFIXES) or line.startswith('- '):
                continue
            if wrap:
                # Continuation lines of a wrapped "Write-In:" row. Resume at the
                # first line that is a recognizable row of its own; a run of
                # bare numbers (the wrapped row's own counts) keeps the wrap.
                m2 = PCT_NUMS.match(line) or FOUR_NUMS.match(line)
                if (line.startswith(('Write-In:', 'Not Assigned', 'Total Votes Cast',
                                     'Overvotes', 'Undervotes', 'TOTAL',
                                     'Contest Totals'))
                        or PRECINCT.match(line) or VOTE_FOR.match(line)
                        or (m2 and re.search(r'[A-Za-z]', m2.group('label')))):
                    wrap = False
                else:
                    continue
            m = PRECINCT.match(line)
            if m:
                # The unit header repeats at the top of every page of its
                # block; start new state only when the label changes.
                if line != unit:
                    unit, contest = line, None
                    stats[unit] = {'rv': None, 'rv_party': {}, 'bc': None,
                                   'blank': None, 'bc_party': {}}
                continue
            if unit is None:
                unparsed.append((unit, line))
                continue
            if line.startswith('Registered Voters - Total'):
                stats[unit]['rv'] = int(ONE_NUM.match(line).group('n').replace(',', ''))
            elif line.startswith('Registered Voters - '):
                mm = ONE_NUM.match(line)
                party = mm.group('label').removeprefix('Registered Voters - ')
                stats[unit]['rv_party'][party] = int(mm.group('n').replace(',', ''))
            elif line.startswith('Ballots Cast - Total'):
                stats[unit]['bc'] = pct_nums(FOUR_NUMS.match(line))
            elif line.startswith('Ballots Cast - Blank'):
                stats[unit]['blank'] = pct_nums(FOUR_NUMS.match(line))
            elif line.startswith('Ballots Cast - '):
                mm = FOUR_NUMS.match(line)
                party = mm.group('label').removeprefix('Ballots Cast - ')
                stats[unit]['bc_party'][party] = pct_nums(mm)
            elif j + 1 < len(lines) and VOTE_FOR.match(lines[j + 1]):
                # Contest header: party-prefixed, or bare for city races.
                cm = CONTEST.match(line)
                if cm:
                    contest = (*normalize_office(cm.group(2).strip()),
                               PARTIES[cm.group(1)])
                else:
                    contest = (*normalize_office(line), '')
            elif contest:
                if line.startswith(('Write-In:', 'Not Assigned', 'Overvotes',
                                    'Undervotes')):
                    # Attributed write-in detail (the "Unofficial" remainder
                    # line), unattributed remainder, and over/undervote counts;
                    # the Write-In Totals row already covers the first two. A
                    # "Write-In:" line without numbers starts a wrapped row.
                    wrap = (line.startswith('Write-In:')
                            and not (PCT_NUMS.match(line) or FOUR_NUMS.match(line)))
                    continue
                if line.startswith('Total Votes Cast'):
                    # Zero-total blocks omit the vote-share column.
                    key = (unit, *contest)
                    totals[key] = add(pct_nums(PCT_NUMS.match(line)
                                               or FOUR_NUMS.match(line)),
                                      totals.get(key))
                    continue
                m2 = PCT_NUMS.match(line) or FOUR_NUMS.match(line)
                if not m2:
                    unparsed.append((unit, line))
                    continue
                candidate = 'Write-in' if line.startswith('Write-In Totals') else flip_name(
                    m2.group('label'))
                candidate = NAME_FIXES.get(candidate, candidate)
                precinct_rows = rows_by_precinct[unit]
                key = (*contest, candidate)
                precinct_rows[key] = add(pct_nums(m2), precinct_rows.get(key))
            else:
                unparsed.append((unit, line))
    return rows_by_precinct, totals, stats, unparsed


def build_rows(rows_by_precinct, stats):
    """Summary rows plus contest rows, one precinct at a time in numeric order."""
    rows = []
    for precinct in sorted(rows_by_precinct, key=lambda p: int(p.split()[0])):
        s = stats[precinct]
        rows.append([COUNTY, precinct, 'Registered Voters', '', '', '', s['rv'], '', '', ''])
        rows.append([COUNTY, precinct, 'Ballots Cast', '', '', '', *s['bc']])
        rows.append([COUNTY, precinct, 'Ballots Cast - Blank', '', '', '', *s['blank']])
        for (office, district, party, candidate), nums in rows_by_precinct[precinct].items():
            rows.append([COUNTY, precinct, office, district, party, candidate, *nums])
    return rows


def summary_contest_totals():
    """Countywide Total Votes Cast per contest from the Cumulative Final Report."""
    expected = {}
    label = None
    with pdfplumber.open(SUMMARY_PATH) as pdf:
        for page in pdf.pages:
            lines = [raw.strip() for raw in (page.extract_text() or '').split('\n')]
            for j, line in enumerate(lines):
                if not line or line.startswith(SKIP_PREFIXES) or line.startswith('- '):
                    continue
                if j + 1 < len(lines) and VOTE_FOR.match(lines[j + 1]):
                    cm = CONTEST.match(line)
                    label = ((*normalize_office(cm.group(2).strip()), PARTIES[cm.group(1)])
                             if cm else (*normalize_office(line), ''))
                elif label and line.startswith('Total Votes Cast'):
                    # Zero-total blocks omit the vote-share column.
                    m2 = PCT_NUMS.match(line) or FOUR_NUMS.match(line)
                    expected[label] = expected.get(label, 0) + int(m2.group('t')
                                                                   .replace(',', ''))
                    label = None
    return expected


def validate(rows_by_precinct, totals, stats, unparsed):
    errors = []
    if unparsed:
        errors.append(f'{len(unparsed)} unparsed lines, e.g. {unparsed[:5]}')

    # Per-unit statistics: party breakdowns must sum to the totals, and every
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

    # Statewide offices x 5 primaries x 55 precincts = 1925; U.S. House,
    # State Senate and State Representative each also 275 (District 6/LD 19
    # covering 43/48 precincts, District 7/LD 21 the remaining 12/7); the
    # Clerk, County Recorder and three Superior Court divisions each on 3
    # parties' ballots (165 blocks each = 825); JP/Constable districts of
    # 11/9/5/5/23/2 precincts likewise on 3 parties (165 blocks each = 330);
    # 2 PCO blocks; 38 city blocks.
    expected_blocks = 1925 + 825 + 825 + 330 + 2 + 38
    if len(totals) != expected_blocks:
        errors.append(f'expected {expected_blocks} contest blocks, found {len(totals)}')
    if sum(1 for k in totals if k[3] == '') != 38:
        errors.append('expected exactly 38 nonpartisan (city) contest blocks')

    # Countywide statistics must match the Cumulative Official Final Report.
    if sum(s['rv'] for s in stats.values()) != EXPECTED_RV_TOTAL:
        errors.append(f'Registered Voters countywide != {EXPECTED_RV_TOTAL}')
    bc_total = [0, 0, 0, 0]
    blank_total = [0, 0, 0, 0]
    rv_party = defaultdict(int)
    bc_party = defaultdict(lambda: [0, 0, 0, 0])
    for s in stats.values():
        bc_total = [a + b for a, b in zip(bc_total, s['bc'])]
        blank_total = [a + b for a, b in zip(blank_total, s['blank'])]
        for party, n in s['rv_party'].items():
            rv_party[party] += n
        for party, nums in s['bc_party'].items():
            bc_party[party] = add(nums, bc_party[party])
    if tuple(bc_total) != EXPECTED_BC:
        errors.append(f'Ballots Cast countywide {tuple(bc_total)} != {EXPECTED_BC}')
    if tuple(blank_total) != EXPECTED_BC_BLANK:
        errors.append(f'Blank countywide {tuple(blank_total)} != {EXPECTED_BC_BLANK}')
    for party, n in EXPECTED_RV_PARTY.items():
        if rv_party[party] != n:
            errors.append(f'RV {party} {rv_party[party]} != {n}')
    for party, n in EXPECTED_BC_PARTY.items():
        if tuple(bc_party[party]) != tuple(n):
            errors.append(f'BC {party} {tuple(bc_party[party])} != {tuple(n)}')

    # Contest totals must match the Cumulative Official Final Report.
    for key, votes in summary_contest_totals().items():
        got = 0
        for contest_rows in rows_by_precinct.values():
            for (office, district, party, _candidate), nums in contest_rows.items():
                if (office, district, party) == key:
                    got += nums[0]
        if got != votes:
            errors.append(f'{key}: precinct total {got} != summary report {votes}')

    # Named state/federal candidates must match the statewide county file
    # (county.csv covers no county or municipal offices for Cochise). It
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
            if candidates.get(key, 0) != int(rec['votes']):
                errors.append(f'county.csv candidate not matched: '
                              f'{rec["candidate"]} {candidates.get(key)} != {rec["votes"]}')

    return errors


def main():
    rows_by_precinct, totals, stats, unparsed = parse_precinct_report()
    rows = build_rows(rows_by_precinct, stats)
    errors = validate(rows_by_precinct, totals, stats, unparsed)

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