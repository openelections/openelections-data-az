#!/usr/bin/env python3
"""Parse Greenlee County's 2026 primary precinct results from the official canvass PDF.

Source: ~/code/openelections-sources-az/2026/primary/Greenlee AZ 2026 Primary
Official Canvass.pdf. PDF pages 39-121 hold the Clarity "Precinct Results
Report" (report pages 1-83 of 83) covering the county's 6 precincts. Each
precinct has a Statistics block (Registered Voters / Ballots Cast / Ballots
Cast - Blank) followed by contest blocks for the REP/DEM/GRN/LIB/NOL primaries
plus the nonpartisan town races (Clifton's council spans precincts 003 and 004;
Duncan's mayor and council are in precinct 006), with vote-method breakdowns:
Election Day, Early Voting, Provisional, Late Early.

In each contest block, Total Votes Cast = named candidates + Write-In Totals;
"Write-In:" rows are the attribution detail under Write-In Totals (skipped
here, along with "Not Assigned", the unattributed remainder).

Writes 2026/counties/20260721__az__primary__greenlee__precinct.csv, then
validates the output: per-contest candidate sums against "Total Votes Cast",
per-precinct statistics against their party breakdowns, countywide contest
totals against the canvass Summary Results Report, and named candidates
against the statewide 2026/20260721__az__primary__county.csv.
"""

import csv
import os
import re
import sys

import pdfplumber

PDF_PATH = os.path.expanduser(
    '~/code/openelections-sources-az/2026/primary/'
    'Greenlee AZ 2026 Primary Official Canvass.pdf'
)
OUTPUT_PATH = '2026/counties/20260721__az__primary__greenlee__precinct.csv'
COUNTY_FILE = '2026/20260721__az__primary__county.csv'
COUNTY = 'Greenlee'
FIRST_PAGE = 39    # PDF page where the Precinct Results Report begins
LAST_PAGE = 121    # PDF page holding report page 83 of 83
FIRST_SUMMARY_PAGE = 3   # Summary Results Report (report pages 1-30 of 30)
LAST_SUMMARY_PAGE = 32

# Countywide figures from the canvass Summary Results Report (PDF page 3).
EXPECTED_RV_TOTAL = 5096
EXPECTED_BC = (965, 164, 696, 3, 102)  # total, election day, early, provisional, late early

# Write-in candidates certified for this election (canvass PDF page 2). They
# appear in county.csv under their own names but inside "Write-In:" detail
# rows here, so they are expected to be absent from the parsed candidates.
CERTIFIED_WRITE_INS = {
    'Bob Karp', 'Gary Swing', 'Athena Maria Eastwood', 'Carlos Melendez',
    'William "Rex" Josué Pounds IV', 'Jon Robert Ralston', 'Mike Cease',
}

PARTIES = {'REP': 'REP', 'DEM': 'DEM', 'GRN': 'GRN', 'LIB': 'LBT', 'NOL': 'NOL'}

SIMPLE_OFFICES = {
    'Governor': 'Governor',
    'Secretary of State': 'Secretary of State',
    'State Treasurer': 'State Treasurer',
    'Attorney General': 'Attorney General',
    'Supt Pub Inst': 'Superintendent of Public Instruction',
    'St Mine Ins': 'State Mine Inspector',
    'Corp Commr': 'Corporation Commissioner',
    'Clk Sup Crt': 'Clerk of the Superior Court',
    'Judge Sup Crt': 'Judge of the Superior Court',
}

# Contest labels with the district embedded in the printed name.
DISTRICTED_OFFICES = [
    (r'U\.S\. Rep Dist (\d+)', 'U.S. House'),
    (r'State Senator (\d+)', 'State Senate'),
    (r'State Rep (\d+)', 'State Representative'),
    (r'Just of Peace (\d+)', 'Justice of the Peace'),
    (r'Constable Precinct (\d+)', 'Constable'),
]

SKIP_PREFIXES = (
    'Precinct Results Report', 'OFFICIAL RESULTS', 'Primary Election', 'CANVASS',
    'July 21,', 'Statistics', 'TOTAL', 'Day Voting', 'Vote For', 'Precinct Summary',
    'Voter Turnout',
)

FIVE_NUMS = re.compile(
    r'^(?P<label>.+?)\s+(?P<t>\d[\d,]*)\s+(?P<ed>\d[\d,]*)\s+(?P<ev>\d[\d,]*)'
    r'\s+(?P<pr>\d[\d,]*)\s+(?P<le>\d[\d,]*)$'
)
ONE_NUM = re.compile(r'^(?P<label>.+?)\s+(?P<n>\d[\d,]*)$')
PRECINCT = re.compile(r'^\d{3}\s+\D')
CONTEST = re.compile(r'^(REP|DEM|LIB|GRN|NOL)\s+(.+)$')


def normalize_office(label):
    """Map a printed contest label to (office, district)."""
    for pattern, office in DISTRICTED_OFFICES:
        m = re.fullmatch(pattern, label)
        if m:
            return office, m.group(1)
    if label in SIMPLE_OFFICES:
        return SIMPLE_OFFICES[label], ''
    m = re.fullmatch(r'Town of (\S+) (.+)', label)
    if m:
        town, race = m.groups()
        district = f'Town of {town}'
        if race == 'Mayor':
            return 'Mayor', district
        m2 = re.fullmatch(r'Council Member( 2 Year Term)?', race)
        if m2:
            return 'Councilmember', district + (m2.group(1) or '')
    raise ValueError(f'Unknown contest label: {label!r}')


def flip_name(raw):
    """'Ciscomani, Juan' -> 'Juan Ciscomani' (spelled first-last like county.csv)."""
    if ',' in raw:
        last, first = raw.split(',', 1)
        return f'{first.strip()} {last.strip()}'
    return raw.strip()


def five_nums(m):
    """(total, election_day, early_voting, provisional, late_early) from a match."""
    return tuple(int(m.group(k).replace(',', '')) for k in ('t', 'ed', 'ev', 'pr', 'le'))


def parse_precinct_report():
    rows, totals, stats, unparsed = [], {}, {}, []
    precinct, cur, contest = None, None, None

    with pdfplumber.open(PDF_PATH) as pdf:
        pages = [pdf.pages[i].extract_text() or '' for i in range(FIRST_PAGE - 1, LAST_PAGE)]

    for text in pages:
        if 'Precinct Results Report' not in text:
            unparsed.append((None, f'unexpected page: {text.splitlines()[0]!r}'))
            continue
        for raw in text.split('\n'):
            line = raw.strip()
            if not line or line.startswith(SKIP_PREFIXES):
                continue
            if PRECINCT.match(line):
                # The precinct header repeats at the top of every page of its
                # block; start a new stats block only when the label changes.
                if line != precinct:
                    precinct, contest = line, None
                    cur = {'rv': None, 'bc': None, 'blank': None,
                           'rv_party': {}, 'bc_party': {}}
                    stats[precinct] = cur
            elif line.startswith('Registered Voters - Total'):
                cur['rv'] = int(ONE_NUM.match(line).group('n').replace(',', ''))
                rows.append([COUNTY, precinct, 'Registered Voters', '', '', '', cur['rv'],
                             '', '', '', ''])
            elif line.startswith('Registered Voters - '):
                cur['rv_party'][line[len('Registered Voters - '):]] = int(
                    ONE_NUM.match(line).group('n').replace(',', ''))
            elif line.startswith('Ballots Cast - Total'):
                cur['bc'] = five_nums(FIVE_NUMS.match(line))
                rows.append([COUNTY, precinct, 'Ballots Cast', '', '', '', *cur['bc']])
            elif line.startswith('Ballots Cast - Blank'):
                cur['blank'] = five_nums(FIVE_NUMS.match(line))
                rows.append([COUNTY, precinct, 'Ballots Cast - Blank', '', '', '', *cur['blank']])
            elif line.startswith('Ballots Cast - '):
                cur['bc_party'][line[len('Ballots Cast - '):]] = five_nums(FIVE_NUMS.match(line))
            elif CONTEST.match(line):
                m = CONTEST.match(line)
                contest = (*normalize_office(m.group(2).strip()), PARTIES[m.group(1)])
            elif line.startswith('Town of '):
                contest = (*normalize_office(line), '')
            elif contest:
                if line.startswith(('Write-In:', 'Not Assigned')):
                    # Attributed write-in detail / unattributed remainder; the
                    # Write-In Totals row already covers both.
                    continue
                if line.startswith('Total Votes Cast'):
                    totals[(precinct, *contest)] = five_nums(FIVE_NUMS.match(line))
                    continue
                m = FIVE_NUMS.match(line)
                if not m:
                    unparsed.append((precinct, line))
                    continue
                candidate = 'Write-in' if line.startswith('Write-In Totals') else flip_name(
                    m.group('label'))
                rows.append([COUNTY, precinct, *contest, candidate, *five_nums(m)])
            else:
                unparsed.append((precinct, line))
    return rows, totals, stats, unparsed


def summary_contest_totals():
    """Countywide Total Votes Cast per contest from the Summary Results Report."""
    expected = {}
    label = None
    with pdfplumber.open(PDF_PATH) as pdf:
        pages = [pdf.pages[i].extract_text() or ''
                 for i in range(FIRST_SUMMARY_PAGE - 1, LAST_SUMMARY_PAGE)]
    for text in pages:
        if 'Summary Results Report' not in text:
            continue
        for raw in text.split('\n'):
            line = raw.strip()
            if CONTEST.match(line):
                m = CONTEST.match(line)
                label = (*normalize_office(m.group(2).strip()), PARTIES[m.group(1)])
            elif line.startswith('Town of '):
                label = (*normalize_office(line), '')
            elif label and line.startswith('Total Votes Cast'):
                m = re.match(r'^Total Votes Cast\s+(\d[\d,]*)', line)
                expected[label] = int(m.group(1).replace(',', ''))
    return expected


def validate(rows, totals, stats, unparsed):
    errors = []
    if unparsed:
        errors.append(f'{len(unparsed)} unparsed lines, e.g. {unparsed[:5]}')

    # Every contest block: candidates + Write-in must equal Total Votes Cast.
    summed = {}
    for r in rows:
        if r[5]:  # skip summary rows, which have no candidate
            key = tuple(r[1:5])
            summed[key] = summed.get(key, 0) + r[6]
    for key, nums in totals.items():
        if summed.get(key) != nums[0]:
            errors.append(f'{key}: candidates+write-in {summed.get(key)} != '
                          f'Total Votes Cast {nums[0]}')
    # 16 offices x 5 primaries across 6 precincts + 6 town blocks, minus the
    # JP/Constable blocks Clarity omits where a district isn't on the ballot:
    # district 1 covers every precinct but Duncan; district 2 covers
    # York/Sheldon and Duncan only.
    expected_blocks = 16 * 5 * 6 + 6 - 5 * (2 + 4 * 2)
    if len(totals) != expected_blocks:
        errors.append(f'expected {expected_blocks} contest blocks, found {len(totals)}')
    if sum(1 for k in totals if k[3] == '') != 6:
        errors.append('expected exactly 6 nonpartisan (town) contest blocks')

    # Statistics: party breakdowns must sum to the totals; methods must sum to votes.
    rv_total, bc_total = 0, [0] * 5
    for precinct, s in stats.items():
        if sum(s['rv_party'].values()) != s['rv']:
            errors.append(f'{precinct}: party registration sum != {s["rv"]}')
        if sum(n[0] for n in s['bc_party'].values()) != s['bc'][0]:
            errors.append(f'{precinct}: party ballots-cast sum != {s["bc"][0]}')
        for row in [s['bc'], s['blank'], *s['bc_party'].values()]:
            if sum(row[1:]) != row[0]:
                errors.append(f'{precinct}: method breakdown {row[1:]} != votes {row[0]}')
        rv_total += s['rv']
        bc_total = [a + b for a, b in zip(bc_total, s['bc'])]
    if rv_total != EXPECTED_RV_TOTAL:
        errors.append(f'Registered Voters countywide {rv_total} != {EXPECTED_RV_TOTAL}')
    if bc_total != list(EXPECTED_BC):
        errors.append(f'Ballots Cast countywide {bc_total} != {EXPECTED_BC}')

    # Contest totals must match the canvass Summary Results Report.
    for key, votes in summary_contest_totals().items():
        got = sum(v for (_p, o, d, pa), v in summed.items() if (o, d, pa) == key)
        if got != votes:
            errors.append(f'{key}: precinct total {got} != summary report {votes}')

    # Named candidates must match the statewide county file (which omits
    # write-in vote totals; certified write-ins live in "Write-In:" rows here).
    candidates = {}
    for r in rows:
        if r[5] and r[5] != 'Write-in':
            key = (r[2], r[3], r[4], r[5])
            candidates[key] = candidates.get(key, 0) + r[6]
    unmatched = []
    with open(COUNTY_FILE, newline='') as f:
        for rec in csv.DictReader(f):
            if rec['county'] != COUNTY or not rec['candidate']:
                continue
            key = (rec['office'], rec['district'], rec['party'], rec['candidate'])
            if candidates.get(key) != int(rec['votes']):
                unmatched.append(rec['candidate'])
    bad = sorted(set(unmatched) - CERTIFIED_WRITE_INS)
    if bad:
        errors.append(f'county.csv candidates not matched: {bad}')

    return errors


def main():
    rows, totals, stats, unparsed = parse_precinct_report()
    errors = validate(rows, totals, stats, unparsed)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['county', 'precinct', 'office', 'district', 'party', 'candidate',
                         'votes', 'election_day', 'early_voting', 'provisional',
                         'late_early_voting'])
        writer.writerows(rows)

    print(f'wrote {len(rows)} rows for {len(stats)} precincts to {OUTPUT_PATH}')
    if errors:
        for e in errors:
            print(f'VALIDATION ERROR: {e}', file=sys.stderr)
        sys.exit(1)
    print('all validations passed')


if __name__ == '__main__':
    main()