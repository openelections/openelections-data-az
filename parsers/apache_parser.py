#!/usr/bin/env python3
"""Parse Apache County's 2026 primary precinct results from Clarity's combined
summary-and-precinct report.

Source: ~/code/openelections-sources-az/2026/primary/Apache AZ 2026 Primary
Official Summary and Precinct Report.pdf (776 pages). PDF page 1 is a blank
cover; pages 2-24 hold the countywide "Summary Results Report" (used here only
as validation anchors); pages 25-776 hold the 752-page precinct report covering
the county's 44 precincts, one Clarity unit per precinct. Unlike the other
counties' reports, candidate rows carry no vote-share column ("NEZ, JONATHAN
41 4 37 0") and the report prints Registered Voters as zero everywhere - per
precinct and countywide alike - so the Registered Voters rows emitted here are
zeros, faithful to the official report.

Each unit has a Statistics block (Registered Voters / Ballots Cast / Ballots
Cast - Blank with per-party and vote-method breakdowns: Election Day, Early,
Provisional) followed by contest blocks for the REP/DEM/GRN/LBT/NOL primaries,
the county offices (including a County Attorney contest), and the nonpartisan
St. Johns/Eagar/Springerville races plus Proposition 409. In each contest
block, Total Votes Cast = named candidates + Write-In Totals; "Write-In:" rows
are the attribution detail (skipped here, along with "Not Assigned" and the
Overvotes/Undervotes counts).

Writes 2026/counties/20260721__az__primary__apache__precinct.csv, then
validates the output: per-contest candidate sums against "Total Votes Cast",
per-precinct statistics against their party breakdowns, countywide statistics
and contest totals against the report's own summary section, and named
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
    'Apache AZ 2026 Primary Official Summary and Precinct Report.pdf'
)
OUTPUT_PATH = '2026/counties/20260721__az__primary__apache__precinct.csv'
COUNTY_FILE = '2026/20260721__az__primary__county.csv'
COUNTY = 'Apache'
FIRST_PAGE = 25    # PDF page where the precinct report begins (after the cover
                   # page and the 23-page countywide summary)

# Countywide figures from the report's summary section (PDF page 2). The 2026
# primary offers three vote methods: Election Day, Early, Provisional. The
# report prints Registered Voters as zero throughout (per precinct and
# countywide alike), so the countywide RV anchor is 0.
EXPECTED_RV_TOTAL = 0
EXPECTED_RV_PARTIES = ('Democratic', 'Republican', 'Green', 'Libertarian',
                       'No Labels', 'Nonpartisan')
EXPECTED_BC = (17077, 7751, 9141, 185)  # total, election day, early, provisional
EXPECTED_BC_PARTY = {
    'Democratic': (11977, 5639, 6199, 139),
    'Republican': (4600, 1791, 2767, 42),
    'Green': (11, 3, 8, 0),
    'Libertarian': (40, 23, 17, 0),
    'No Labels': (440, 288, 148, 4),
    'Nonpartisan': (9, 7, 2, 0),
}
EXPECTED_BC_BLANK = (32, 23, 9, 0)

# Precinct labels as printed ("02 ALPINE"), title-cased to match the county's
# 2020-2022 precinct files; these three need more than .title() gives.
PRECINCT_FIXES = {
    'Ft. Defiance': 'Ft Defiance',
    'St. Johns': 'St Johns',
    'St. Michaels': 'St Michaels',
    'Mcnary': 'McNary',
}
EXPECTED_PRECINCTS = {
    '02 Alpine', '03 Canyon De Chelly', '05 Chinle', '09 Concho', '10 Cornfields',
    '11 Cottonwood', '12 Coronado', '13 Dennehotso', '16 Eagar', '17 Flat Top',
    '19 Ft Defiance', '22 Ganado North', '23 Ganado South', '25 Greer', '27 Houck',
    '29 Kinlichee', '31 Klagetoh', '33 Lukachukai', '35 Lupton', '37 McNary',
    '39 Many Farms', '41 Mexican Water', '43 Nazlini', '45 Nutrioso',
    '46 Oak Springs', '48 Puerco', '51 Red Mesa', '52 Red Valley', '54 Rock Point',
    '56 Rough Rock', '58 Round Rock', '59 Round Valley', '61 St Johns',
    '65 St Michaels', '67 Sawmill', '70 Springerville', '74 Steamboat',
    '76 Sweetwater', '78 Tachee', '80 Teec Nos Pos', '82 Vernon',
    '84 Wheatfields', '86 Wide Ruins', '88 Window Rock',
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
    'County Attorney': 'County Attorney',
}

# Contest labels with the district (or justice-court precinct) embedded in the
# printed name. "Dist.2" is printed without a space in this county's report.
DISTRICTED_OFFICES = [
    (r'U\.S\. Representative in Congress Dist\.\s*(\d+)', 'U.S. House'),
    (r'State Senator Dist\.\s*(\d+)', 'State Senate'),
    (r'State Representative Dist\.\s*(\d+)', 'State Representative'),
    (r'Justice of the Peace - (.+)', 'Justice of the Peace'),
    (r'Constable - (.+)', 'Constable'),
]

SKIP_PREFIXES = (
    'Summary Results Report', 'AZ Apache County', 'July 21, 2026 County of Apache',
    'Statistics', 'TOTAL', 'Day', 'Vote For', 'Voter Turnout',
    'Election Day Precincts', 'Precincts', 'Absentee/ Early',
    'Election Summary', 'Precinct Summary',
)

FOUR_NUMS = re.compile(
    r'^(?P<label>.+?)\s+(?P<t>\d[\d,]*)\s+(?P<ed>\d[\d,]*)\s+(?P<ev>\d[\d,]*)'
    r'\s+(?P<pr>\d[\d,]*)$'
)
ONE_NUM = re.compile(r'^(?P<label>.+?)\s+(?P<n>\d[\d,]*)$')
# Unit header: precinct number plus all-caps name (repeats at page tops).
PRECINCT = re.compile(r'^(?P<num>\d{1,3})\s+(?P<name>[A-Z][A-Z./ ]+)$')
CONTEST = re.compile(r'^(REP|DEM|GRN|LBT|NOL)\s+(.+)$')
VOTE_FOR = re.compile(r'^Vote For \d+$')


def precinct_label(m):
    """'02 ALPINE' -> '02 Alpine' (2020-2022 file spelling)."""
    name = m.group('name').strip().title()
    return f'{m.group("num")} {PRECINCT_FIXES.get(name, name)}'


def normalize_office(label):
    """Map a printed contest label to (office, district)."""
    for pattern, office in DISTRICTED_OFFICES:
        m = re.fullmatch(pattern, label)
        if m:
            return office, m.group(1).strip()
    if label in SIMPLE_OFFICES:
        return SIMPLE_OFFICES[label], ''
    m = re.fullmatch(r'(Mayor|Council Member) - (City|Town) of (.+)', label)
    if m:
        return 'Mayor' if m.group(1) == 'Mayor' else 'Councilmember', \
            f'{m.group(2)} of {m.group(3)}'
    m = re.fullmatch(r'PROPOSITION (\d+)\s+(?:City|Town) of (.+)', label)
    if m:
        return f'Proposition {m.group(1)}', f'Town of {m.group(2)}'
    raise ValueError(f'Unknown contest label: {label!r}')


def flip_name(raw):
    """'NEZ, JONATHAN' -> 'Jonathan Nez' (spelled first-last like county.csv)."""
    if ',' in raw:
        last, first = raw.split(',', 1)
        return f'{first.strip()} {last.strip()}'.title()
    return raw.strip()  # e.g. proposition choices YES / NO, printed as-is


def four_nums(m):
    """(total, election_day, early_voting, provisional) from a match."""
    return tuple(int(m.group(k).replace(',', '')) for k in ('t', 'ed', 'ev', 'pr'))


def add(nums, held):
    """Componentwise vote sum; keeps per-precinct state across page-top repeats."""
    return list(nums) if held is None else [a + b for a, b in zip(held, nums)]


def candidate_row(line):
    """Parse a candidate/Write-In Totals row, or None."""
    m = FOUR_NUMS.match(line)
    if not m:
        return None
    candidate = 'Write-in' if line.startswith('Write-In Totals') else flip_name(
        m.group('label'))
    return candidate, four_nums(m)


def parse_precinct_report():
    """Parse the 44 precinct units from the report's precinct section."""
    rows_by_precinct = defaultdict(dict)  # precinct -> {(o, d, p, cand): [t, ed, ev, pr]}
    totals = {}   # (precinct, office, district, party) -> [t, ed, ev, pr]
    stats = {}    # precinct -> {'rv', 'rv_party', 'bc', 'blank', 'bc_party'}
    unparsed = []
    precinct, contest, unit = None, None, None
    wrap = False  # inside a "Write-In:" row whose long name wraps across lines

    with pdfplumber.open(PDF_PATH) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages[FIRST_PAGE - 1:]]

    for text in pages:
        lines = [raw.strip() for raw in text.split('\n')]
        for j, line in enumerate(lines):
            if not line or line.startswith(SKIP_PREFIXES):
                continue
            if wrap:
                # Continuation lines of a wrapped "Write-In:" row. Resume at the
                # first line that is a recognizable row of its own; a run of
                # bare numbers (the wrapped row's own counts) keeps the wrap.
                m4 = FOUR_NUMS.match(line)
                if (line.startswith(('Write-In:', 'Not Assigned', 'Total Votes Cast',
                                     'Overvotes', 'Undervotes', 'TOTAL'))
                        or PRECINCT.match(line) or VOTE_FOR.match(line)
                        or (m4 and re.search(r'[A-Za-z]', m4.group('label')))):
                    wrap = False
                else:
                    continue
            m = PRECINCT.match(line)
            if m:
                # The unit header repeats at the top of every page of its
                # block; start new state only when the label changes.
                if line != precinct:
                    precinct, contest = line, None
                    unit = precinct_label(m)
                    stats[unit] = {'rv': None, 'rv_party': {}, 'bc': None,
                                   'blank': None, 'bc_party': {}}
                continue
            if precinct is None:
                unparsed.append((unit, line))
                continue
            if line.startswith('Registered Voters - Total'):
                stats[unit]['rv'] = int(ONE_NUM.match(line).group('n').replace(',', ''))
            elif line.startswith('Registered Voters - '):
                mm = ONE_NUM.match(line)
                party = mm.group('label').removeprefix('Registered Voters - ')
                stats[unit]['rv_party'][party] = int(mm.group('n').replace(',', ''))
            elif line.startswith('Ballots Cast - Total'):
                stats[unit]['bc'] = four_nums(FOUR_NUMS.match(line))
            elif line.startswith('Ballots Cast - Blank'):
                stats[unit]['blank'] = four_nums(FOUR_NUMS.match(line))
            elif line.startswith('Ballots Cast - '):
                mm = FOUR_NUMS.match(line)
                party = mm.group('label').removeprefix('Ballots Cast - ')
                stats[unit]['bc_party'][party] = four_nums(mm)
            elif j + 1 < len(lines) and VOTE_FOR.match(lines[j + 1]):
                # Contest header: party-prefixed, or bare for the nonpartisan
                # city/town races and proposition.
                cm = CONTEST.match(line)
                if cm:
                    contest = (*normalize_office(cm.group(2).strip()),
                               PARTIES[cm.group(1)])
                else:
                    contest = (*normalize_office(line), '')
            elif contest:
                if line.startswith(('Write-In:', 'Not Assigned', 'Overvotes',
                                    'Undervotes')):
                    # Attributed write-in detail, unattributed remainder, and
                    # over/undervote counts; the Write-In Totals row already
                    # covers the first two. A "Write-In:" line without any
                    # numbers is the first piece of a wrapped row.
                    wrap = (line.startswith('Write-In:')
                            and not FOUR_NUMS.match(line))
                    continue
                if line.startswith('Total Votes Cast'):
                    key = (unit, *contest)
                    totals[key] = add(four_nums(FOUR_NUMS.match(line)),
                                      totals.get(key))
                    continue
                row = candidate_row(line)
                if not row:
                    unparsed.append((unit, line))
                    continue
                precinct_rows = rows_by_precinct[unit]
                key = (*contest, row[0])
                precinct_rows[key] = add(row[1], precinct_rows.get(key))
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
    """Countywide Total Votes Cast per contest from the report's summary section."""
    expected = {}
    label = None
    with pdfplumber.open(PDF_PATH) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages[:FIRST_PAGE - 1]]
    for text in pages:
        lines = [raw.strip() for raw in text.split('\n')]
        for j, line in enumerate(lines):
            if not line or line.startswith(SKIP_PREFIXES):
                continue
            if j + 1 < len(lines) and VOTE_FOR.match(lines[j + 1]):
                cm = CONTEST.match(line)
                label = ((*normalize_office(cm.group(2).strip()), PARTIES[cm.group(1)])
                         if cm else (*normalize_office(line), ''))
            elif label and line.startswith('Total Votes Cast'):
                votes = int(line.removeprefix('Total Votes Cast').strip().split()[0]
                            .replace(',', ''))
                expected[label] = expected.get(label, 0) + votes
                label = None
    return expected


def validate(rows_by_precinct, totals, stats, unparsed):
    errors = []
    if unparsed:
        errors.append(f'{len(unparsed)} unparsed lines, e.g. {unparsed[:5]}')

    # Per-precinct statistics: party breakdowns must sum to the totals, and
    # every vote-method breakdown must sum to its vote count.
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

    # 5 primaries x (13 offices x 44 precincts + JP + Constable), where the
    # justice-court districts of North Star (32 precincts), Round Valley (9)
    # and St. Johns (3) together cover all 44; plus 14 city/town blocks
    # (St. Johns and Eagar/Springerville councils, Springerville mayor,
    # Proposition 409).
    expected_blocks = 5 * (13 * 44 + 44 + 44) + 14
    if len(totals) != expected_blocks:
        errors.append(f'expected {expected_blocks} contest blocks, found {len(totals)}')
    if sum(1 for k in totals if k[3] == '') != 14:
        errors.append('expected exactly 14 nonpartisan (city/town) contest blocks')

    # Countywide statistics must match the summary section.
    if sum(s['rv'] for s in stats.values()) != EXPECTED_RV_TOTAL:
        errors.append(f'Registered Voters countywide != {EXPECTED_RV_TOTAL}')
    bc_total = [0, 0, 0, 0]
    blank_total = [0, 0, 0, 0]
    rv_party = defaultdict(int)
    bc_party = defaultdict(lambda: [0, 0, 0, 0])
    for s in stats.values():
        bc_total = [a + b for a, b in zip(bc_total, s['bc'])]
        blank_total = [a + b for a, b in zip(blank_total, s['blank'])]
        for party in EXPECTED_RV_PARTIES:
            rv_party[party] += s['rv_party'].get(party, 0)
        for party, nums in s['bc_party'].items():
            bc_party[party] = add(nums, bc_party[party])
    if tuple(bc_total) != EXPECTED_BC:
        errors.append(f'Ballots Cast countywide {tuple(bc_total)} != {EXPECTED_BC}')
    if tuple(blank_total) != EXPECTED_BC_BLANK:
        errors.append(f'Blank countywide {tuple(blank_total)} != {EXPECTED_BC_BLANK}')
    for party, n in EXPECTED_BC_PARTY.items():
        if tuple(bc_party[party]) != tuple(n):
            errors.append(f'BC {party} {tuple(bc_party[party])} != {tuple(n)}')

    # Contest totals must match the summary section.
    for key, votes in summary_contest_totals().items():
        got = 0
        for contest_rows in rows_by_precinct.values():
            for (office, district, party, _candidate), nums in contest_rows.items():
                if (office, district, party) == key:
                    got += nums[0]
        if got != votes:
            errors.append(f'{key}: precinct total {got} != summary report {votes}')

    # Named state/federal candidates must match the statewide county file
    # (county.csv covers no county or municipal offices for Apache). It carries
    # no district for these offices, so match on office/party/candidate. Rows
    # it flags as write-ins live only in "Write-In:" detail rows here, so they
    # are exempt from the vote comparison.
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