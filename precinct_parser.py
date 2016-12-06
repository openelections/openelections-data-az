import requests
import unicodecsv

HEADERS = {
    'Apache': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'polling_place_votes_ds200', 'early_votes_ds200', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Cochise': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Coconino': 'GEMS',
    'Gila': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Graham': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Greenlee': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'La Paz': 'GEMS',
    'Maricopa': 'WinEDS',
    'Mohave': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Navajo': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'late_early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'votes_allowed', 'referendum_flag'],
    'Pima': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Pinal': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'late_early_votes', 'provisional_votes', 'polling_place_votes_ds200', 'early_votes_ds200', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Santa Cruz': 'ElectionWare',
    'Yavapai': 'OpenElect',
    'Yuma': 'GEMS'
}

def fetch_url(year, election, county):
    return "http://apps.azsos.gov/results/%s/%s/%s.txt" % (year, election, county)

def fetch_headers(county):
    return HEADERS[county]

def parse_county(year, election, county):
    results = []
    url = fetch_url(year, election, county)
    r = requests.get(url)
    lines = r.text
    results = parse_county_lines(county, lines)
    write_csv(results, county)

def parse_county_lines(county, lines):
    results = []
    if county == 'Apache':
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:16], line[17:22], line[23:28], line[29:34], line[35:40], line[41:46], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:206], line[207:233].strip(), line[234:259].strip(), line[260:261], line[262:263]])
    elif county in ['Cochise', 'Gila', 'Graham', 'Greenlee', 'Mohave', 'Pima']:
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:16], line[17:22], line[23:28], line[29:34], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:234].strip(), line[260:261], line[262:263]])
    elif county in ['Navajo']:
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:16], line[17:22], line[23:28], line[29:34], line[35:40], line[41:46], line[101:105].strip(), line[111:166].strip(), line[167:204].strip(), line[207:234].strip(), line[260:261], line[262:263]])
    return results

def write_csv(results, county):
    headers = HEADERS[county]
    filename = '20161108__az__general__%s__precinct.csv' % county.lower().replace(' ','_')
    with open(filename, 'wb') as csvfile:
         w = unicodecsv.writer(csvfile, encoding='utf-8')
         w.writerow(headers)
         for row in results:
             w.writerow(row)
