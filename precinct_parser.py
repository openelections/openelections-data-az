import requests
import unicodecsv

HEADERS = {
    'Apache': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'polling_place_votes_ds200', 'early_votes_ds200', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Cochise': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Coconino': ['', 'precinct_id', 'precinct_name', '', 'contest', 'contest_name', '', '', '', '', '', '', '', 'choice', 'choice_name', '', '', 'party', 'candidate_party', 'vote_type_id', 'vote_type', '', 'vote_total'],
    'Gila': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Graham': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Greenlee': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'La Paz': ['', 'precinct_id', 'precinct_name', '', 'contest', 'contest_name', '', '', '', '', '', '', '', 'choice', 'choice_name', '', '', 'party', 'candidate_party', 'vote_type_id', 'vote_type', '', 'vote_total'],
    'Maricopa': ['precinct_name', 'choice_name', 'party_id', 'candidate_id', 'contest_type', 'contest', 'contest_order_id', 'choice_order', 'contest_name', 'vote_total', 'precinct_id', 'precinct_order', 'votes_allowed', 'processed_done', 'processed_started', 'contest_total', 'write_in', 'undervote', 'overvote'],
    'Mohave': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Navajo': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'late_early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'votes_allowed', 'referendum_flag'],
    'Pima': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Pinal': ['contest', 'choice', 'precinct_id', 'vote_total', 'early_votes', 'polling_place_votes', 'late_early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_designation', 'precinct_name', 'votes_allowed', 'referendum_flag'],
    'Santa Cruz': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'polling_place_votes_ds200', 'early_votes_ds200', 'party_name', 'contest_name', 'choice_name', 'precinct_name', 'votes_allowed', 'referendum_flag'],
    'Yavapai': ['record_type','precinct_id','precinct_name','contest','vote_for_value','contest_order_id','contest_name','candidate_name','party_name','candidate_id', 'vote_total', 'vote_type', 'done'],
    'Yuma': ['', 'precinct_id', 'precinct_name', '', 'contest', 'contest_name', '', '', '', '', '', '', '', 'choice', 'choice_name', '', '', 'party', 'candidate_party', 'vote_type_id', 'vote_type', '', 'vote_total']
}

def parse_all(year, election):
    for county in HEADERS.keys():
        parse_county(year, election, county)

def fetch_url(year, election, county):
    return "http://apps.azsos.gov/results/%s/%s/%s.txt" % (year, election, county)

def fetch_headers(county):
    return HEADERS[county]

def parse_county(year, election, county):
    results = []
    url = fetch_url(year, election, county)
    r = requests.get(url)
    lines = r.text.encode('utf-8')
    results = parse_county_lines(county, lines)
    write_csv(results, county)

def parse_county_lines(county, lines):
    results = []
    if county == 'Apache':
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:17], line[18:23], line[23:28], line[29:34], line[35:40], line[41:46], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:206], line[207:233].strip(), line[234:259].strip(), line[260:261], line[262:263]])
    elif county in ['Cochise', 'Gila', 'Graham', 'Greenlee', 'Pima', 'Mohave']:
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:17], line[18:23], line[24:29], line[30:35], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:234].strip(), line[260:261], line[262:263]])
    elif county == 'Pinal':
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:17], line[18:23], line[23:28], line[29:34], line[35:40], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:206], line[207:234].strip(), line[260:261], line[262:263]])
    elif county in ['Navajo']:
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:17], line[18:23], line[23:28], line[29:34], line[35:40], line[41:46], line[101:105].strip(), line[111:166].strip(), line[167:204].strip(), line[207:234].strip(), line[260:261], line[262:263]])
    elif county == 'Santa Cruz':
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:17], line[18:23], line[23:28], line[29:34], line[35:40], line[41:46], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:234].strip(), line[260:261], line[262:263]])
    elif county in ['Coconino', 'La Paz', 'Yuma']:
        reader = unicodecsv.reader(lines.split('\r\n'), encoding='utf-8')
        for row in reader:
            results.append(list(row))
    elif county == 'Yavapai':
        reader = unicodecsv.reader(lines.splitlines()[3:], encoding='utf-8')
        for row in reader:
            results.append(list(row))
    elif county == 'Maricopa':
        reader = unicodecsv.reader(lines.splitlines()[1:], dialect=unicodecsv.excel_tab, encoding='utf-8')
        for row in reader:
            results.append(list(row))
    return results

def write_csv(results, county):
    headers = HEADERS[county]
    filename = '20161106__az__general__%s__precinct.csv' % county.lower().replace(' ','_')
    with open(filename, 'wb') as csvfile:
         w = unicodecsv.writer(csvfile, encoding='utf-8')
         w.writerow(headers)
         for row in results:
             w.writerow(row)
