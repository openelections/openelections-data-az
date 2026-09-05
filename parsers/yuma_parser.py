#!/usr/bin/env python3
"""Parse Yuma County's 2026 primary precinct results from Clarity's detail XML.

Source: ~/code/openelections-sources-az/2026/primary/Yuma AZ 2026 Primary
detail.xml (Clarity's Election Result snapshot export; the county posted no
canvass or summary report alongside it). The XML carries 47 precincts with
registration and turnout (VoterTurnout block) and 49 contests, each a list of
Choices (candidates) whose vote-method breakdowns - Election Day, Early
Voting, Provisional, Late Early - are given per precinct. Precincts are
numbered only ("PRECINCT 001"); the labels here match the county's older
files ("001"). There are no Libertarian contest blocks in the export (none of
the county's Libertarian votes were attributed to named candidates), and no
write-in choices; county.csv rows flagged as write-ins cover those votes. The
one PCO race ("Precinct Committeemen 39") is office Precinct Committeeman in
district 39, matching Maricopa's 2026 file. Candidate nicknames are printed
in single quotes ("PRESMYK, WALTER 'LES'") and re-quoted with double quotes
to match county.csv ("Walter "Les" Presmyk").

Writes 2026/counties/20260721__az__primary__yuma__precinct.csv, then
validates the output: every vote-method breakdown against its countywide
VoteType total, each candidate's per-precinct sums against their Choice
totalVotes, countywide registration/turnout, and named state/federal
candidates against the statewide 2026/20260721__az__primary__county.csv.
"""

import csv
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

XML_PATH = os.path.expanduser(
    '~/code/openelections-sources-az/2026/primary/Yuma AZ 2026 Primary detail.xml'
)
OUTPUT_PATH = '2026/counties/20260721__az__primary__yuma__precinct.csv'
COUNTY_FILE = '2026/20260721__az__primary__county.csv'
COUNTY = 'Yuma'

# Countywide figures from the XML's VoterTurnout block (the county posted no
# separate summary report to check them against).
EXPECTED_RV_TOTAL = 109840
EXPECTED_BC_TOTAL = 22267

PARTIES = {'REP': 'REP', 'DEM': 'DEM', 'GRN': 'GRN', 'LBT': 'LBT', 'NOL': 'NOL'}

SIMPLE_OFFICES = {
    'Governor': 'Governor',
    'Secretary of State': 'Secretary of State',
    'State Treasurer': 'State Treasurer',
    'Attorney General': 'Attorney General',
    'Superintendent of Public Instruction': 'Superintendent of Public Instruction',
    'State Mine Inspector': 'State Mine Inspector',
    'Corporation Commissioner': 'Corporation Commissioner',
    'Clerk of Superior Court': 'Clerk of the Superior Court',
}

DISTRICTED_OFFICES = [
    (r'U\.S\. Representative in Congress District No\. (\d+)', 'U.S. House'),
    (r'State Senator District No\. (\d+)', 'State Senate'),
    (r'State Representative District No\. (\d+)', 'State Representative'),
    (r'Judge of Superior Court Div\. (\d+)', 'Judge of the Superior Court'),
    (r'Justice of the Peace Prec\. (\d+)', 'Justice of the Peace'),
    (r'Constable Prec\. (\d+)', 'Constable'),
    (r'Precinct Committeemen (\d+)', 'Precinct Committeeman'),
]

# county.csv spellings that the XML prints differently.
NAME_FIXES = {
    'Michele Pena': 'Michele Peña',
}


def normalize_office(label):
    """Map a printed contest label to (office, district)."""
    for pattern, office in DISTRICTED_OFFICES:
        m = re.fullmatch(pattern, label)
        if m:
            return office, m.group(1)
    if label in SIMPLE_OFFICES:
        return SIMPLE_OFFICES[label], ''
    m = re.fullmatch(r'(City|Town) of (.+) (Mayor|Council Member|'
                     r'Presiding Municipal Judge)', label)
    if m:
        office = 'Mayor' if m.group(3) == 'Mayor' else 'Councilmember'
        if m.group(3) == 'Presiding Municipal Judge':
            office = 'Presiding Municipal Judge'
        return office, f'{m.group(1)} of {m.group(2)}'
    raise ValueError(f'Unknown contest label: {label!r}')


def precinct_label(raw):
    """'PRECINCT 001' -> '001' (the county's older files use bare numbers)."""
    return re.search(r'\d+', raw).group()


def flip_name(raw):
    """'BUTIEREZ SR., DANIEL FRANCIS' -> 'Daniel Francis Butierez Sr.'-style."""
    if ',' in raw:
        last, first = raw.split(',', 1)
        return f'{first.strip()} {last.strip()}'.title()
    return raw.strip()


def nickname_quotes(raw):
    """'PRESMYK, WALTER 'LES'' -> 'PRESMYK, WALTER "LES"' (county.csv quotes
    nicknames with double quotes). O'-style apostrophes (letter'letter) and
    quotes touching other quotes are preserved."""
    out = []
    for i, ch in enumerate(raw):
        opening = i == 0 or raw[i - 1] in " \t\"'"
        closing = i == len(raw) - 1 or raw[i + 1] in " \t\"'"
        out.append('"' if ch == "'" and (opening or closing) else ch)
    return ''.join(out)


def choice_candidate(raw):
    """Choice text -> candidate name per repo conventions."""
    name = flip_name(nickname_quotes(raw))
    return NAME_FIXES.get(name, name)


def parse_xml(errors):
    """Parse precinct turnout and contest rows, checking each Choice's
    per-precinct method breakdowns against their countywide totals."""
    stats = {}     # precinct -> {'rv': int, 'bc': int}
    rows_by_precinct = defaultdict(dict)  # precinct -> {(o,d,p,cand): [t,ed,ev,pr,le]}

    root = ET.parse(XML_PATH).getroot()
    turnout = root.find('VoterTurnout')
    for precinct in turnout.find('Precincts'):
        stats[precinct_label(precinct.get('name'))] = {
            'rv': int(precinct.get('totalVoters')),
            'bc': int(precinct.get('ballotsCast')),
        }

    for contest in root.iter('Contest'):
        text = contest.get('text')
        cm = re.match(r'(REP|DEM|GRN|LBT|NOL) (.+)', text)
        if cm:
            party, label = PARTIES[cm.group(1)], cm.group(2)
        else:
            party, label = '', text
        office, district = normalize_office(label)

        for choice in contest.iter('Choice'):
            candidate = choice_candidate(choice.get('text'))
            method_sum = 0
            for votetype in choice.iter('VoteType'):
                method = votetype.get('name')
                method_votes = int(votetype.get('votes'))
                method_sum += method_votes
                precinct_sum = 0
                for precinct in votetype.iter('Precinct'):
                    label_ = precinct_label(precinct.get('name'))
                    votes = int(precinct.get('votes'))
                    precinct_sum += votes
                    prow = rows_by_precinct[label_].setdefault(
                        (office, district, party, candidate), [0, 0, 0, 0, 0])
                    idx = {'Election Day': 1, 'Early Voting': 2, 'Provisional': 3,
                           'Late Early': 4}[method]
                    prow[0] += votes
                    prow[idx] += votes
                if precinct_sum != method_votes:
                    errors.append(f'{text} / {candidate} {method}: precincts '
                                  f'{precinct_sum} != countywide {method_votes}')
            if method_sum != int(choice.get('totalVotes')):
                errors.append(f'{text} / {candidate}: methods {method_sum} != '
                              f'totalVotes {choice.get("totalVotes")}')
    return stats, rows_by_precinct


def build_rows(stats, rows_by_precinct):
    """Summary rows (registration/turnout only; the XML has no blank-ballot
    counts) plus contest rows, one precinct at a time in numeric order."""
    rows = []
    for precinct in sorted(rows_by_precinct, key=lambda p: int(p)):
        s = stats[precinct]
        rows.append([COUNTY, precinct, 'Registered Voters', '', '', '', s['rv'], '', '', '', ''])
        rows.append([COUNTY, precinct, 'Ballots Cast', '', '', '', s['bc'], '', '', '', ''])
        for (office, district, party, candidate), nums in rows_by_precinct[precinct].items():
            rows.append([COUNTY, precinct, office, district, party, candidate, *nums])
    return rows


def validate(stats, rows_by_precinct):
    errors = []
    if set(stats) != set(rows_by_precinct):
        errors.append(f'precincts mismatch: {set(stats) ^ set(rows_by_precinct)}')

    # Countywide registration/turnout.
    if sum(s['rv'] for s in stats.values()) != EXPECTED_RV_TOTAL:
        errors.append(f'Registered Voters countywide != {EXPECTED_RV_TOTAL}')
    if sum(s['bc'] for s in stats.values()) != EXPECTED_BC_TOTAL:
        errors.append(f'Ballots Cast countywide != {EXPECTED_BC_TOTAL}')

    # Named state/federal candidates must match the statewide county file
    # (county.csv covers no county or municipal offices for Yuma). It carries
    # no district for these offices, so match on office/party/candidate. Rows
    # it flags as write-ins never appear as Choices in the XML, so they are
    # exempt from the vote comparison.
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
    errors = []
    stats, rows_by_precinct = parse_xml(errors)
    rows = build_rows(stats, rows_by_precinct)
    errors += validate(stats, rows_by_precinct)

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