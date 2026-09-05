import requests
import csv

COUNTIES = {
    'Apache': '6967.Apache.Detail',
    'Cochise': '6970.Cochise.Detail',
    'Coconino': '6975.Coconino.Detail',
    'Gila': '6972.Gila_.Detail',
    'Graham': '6887.Graham.Detail',
    'Greenlee': '6841.Greenlee.Detail',
    'La Paz': '6957.La%20Paz.Detail',
    'Maricopa': '6989.Maricopa.Detail',
    'Mohave': '6969.Mohave.Detail',
    'Navajo': '6955.Navajo.Detail',
    'Pima': '6981.Pima_.Detail',
    'Pinal': '6956.Pinal_.Detail',
    'Santa Cruz': '6971.Santa%20Cruz.Detail',
    'Yavapai': '6988.Yavapai.Detail',
    'Yuma': '6979.Yuma_.Detail'
}

HEADERS = {
    'Apache': ['contest', 'choice', 'precinct_id', 'vote_total', 'early_votes', 'polling_place_votes',  'provisional_votes', 'polling_place_votes_ds200', 'early_votes_ds200', 'provisional_votes_ds200', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Cochise': ['contest', 'choice', 'precinct_id', 'vote_total', 'early_votes', 'polling_place_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Coconino': ['', 'precinct_id', 'precinct_name', '', 'contest', 'contest_name', '', '', '', '', '', '', '', 'choice', 'choice_name', '', '', 'party', 'candidate_party', 'vote_type_id', 'vote_type', '', 'vote_total'],
    'Gila': ['contest', 'choice', 'precinct_id', 'vote_total', 'early_votes', 'polling_place_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Graham': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'provisional_votes_ds200', 'party_name', 'contest_name', 'choice_name', 'precinct_name', 'votes_allowed', 'referendum_flag'],
    'Greenlee': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'provisional_votes_ds200', 'party_name', 'contest_name', 'choice_name', 'precinct_name', 'votes_allowed', 'referendum_flag'],
    'La Paz': ['contest', 'choice', 'precinct_id', 'vote_total', 'early_votes', 'polling_place_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'votes_allowed', 'referendum_flag'],
    'Maricopa': ['precinct_name', 'choice_name', 'party_id', 'candidate_id', 'contest_type', 'contest', 'contest_order_id', 'choice_order', 'contest_name', 'vote_total', 'precinct_id', 'precinct_order', 'votes_allowed', 'processed_done', 'processed_started', 'contest_total', 'write_in', 'undervote', 'overvote'],
    'Mohave': ['contest', 'choice', 'precinct_id', 'vote_total', 'early_votes', 'polling_place_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Navajo': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'late_early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_name', 'votes_allowed', 'referendum_flag'],
    'Pima': ['contest', 'choice', 'precinct_id', 'vote_total', 'early_votes', 'polling_place_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
    'Pinal': ['contest', 'choice', 'precinct_id', 'vote_total', 'early_votes', 'polling_place_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'votes_allowed', 'referendum_flag'],
    'Santa Cruz': ['contest', 'choice', 'precinct_id', 'vote_total', 'polling_place_votes', 'early_votes', 'provisional_votes', 'early_votes_ds200', 'party_name', 'contest_name', 'choice_name', 'precinct_name', 'votes_allowed', 'referendum_flag'],
    'Yavapai': ['record_type','precinct_id','precinct_name','contest','vote_for_value','contest_order_id','contest_name','candidate_name','party_name','candidate_id', 'vote_total', 'vote_type', 'reporting'],
    'Yuma': ['contest', 'choice', 'precinct_id', 'vote_total', 'early_votes', 'election_day', 'late_early_votes', 'provisional_votes', 'party_name', 'contest_name', 'choice_name', 'precinct_designation', 'precinct_name', 'subjurisdiction', 'votes_allowed', 'referendum_flag'],
}

def parse_all():
    for county in HEADERS.keys():
        county_slug = COUNTIES[county]
        parse_county(county, county_slug)

def fetch_url(county_slug):
    return "https://azsos.gov/sites/default/files/%s.txt" % (county_slug)

def fetch_headers(county):
    return HEADERS[county]

def parse_county(county, county_slug):
    results = []
    url = fetch_url(county_slug)
    r = requests.get(url)
    lines = r.text
    results = parse_county_lines(county, lines)
    write_csv(results, county)

def parse_county_lines(county, lines):
    results = []
    if county == 'Apache':
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:16], line[17:22], line[23:28], line[29:34], line[35:40], line[41:46], line[47:51], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:206], line[207:233].strip(), line[234:259].strip(), line[260:261], line[262:263]])
    elif county in ['Graham', 'Greenlee']:
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:16], line[17:22], line[23:28], line[29:34], line[35:40], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:235].strip(), line[260:261], line[262:263]])
    elif county in ['La Paz']:
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:16], line[17:22], line[23:28], line[29:34], line[35:40], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:206], line[207:234], line[260:261], line[262:263]])
    elif county in ['Cochise', 'Gila', 'Pima', 'Mohave']:
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:16], line[17:22], line[23:28], line[29:34], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:234].strip(), line[260:261], line[262:263]])
    elif county == 'Pinal':
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:16], line[17:22], line[23:28], line[29:34], line[35:40], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:206], line[207:234].strip(), line[260:261], line[262:263]])
    elif county in ['Navajo']:
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:17], line[18:23], line[23:28], line[29:34], line[35:40], line[41:46], line[101:105].strip(), line[111:166].strip(), line[167:204].strip(), line[207:234].strip(), line[260:261], line[262:263]])
    elif county == 'Santa Cruz':
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:16], line[17:22], line[23:28], line[29:34], line[35:40], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:234].strip(), line[260:261], line[262:263]])
    elif county in ['Coconino']:
        reader = csv.reader(lines.split('\r\n'))
        for row in reader:
            results.append(list(row))
    elif county == 'Yavapai':
        reader = csv.reader(lines.splitlines()[3:])
        for row in reader:
            results.append(list(row))
    elif county == 'Yuma':
        for line in lines.split('\r\n'):
            results.append([line[0:3], line[4:6], line[7:10], line[11:16], line[17:22], line[23:28], line[29:34], line[35:40], line[101:104].strip(), line[111:166].strip(), line[167:204].strip(), line[205:233].strip(), line[234:259].strip(), line[260:261], line[262:263]])
    elif county == 'Maricopa':
        reader = csv.reader(lines.splitlines()[1:], dialect=csv.excel_tab)
        for row in reader:
            results.append(list(row))
    return results

def write_csv(results, county):
    headers = HEADERS[county]
    filename = '20181106__az__general__%s__precinct.csv' % county.lower().replace(' ','_')
    with open(filename, 'w') as csvfile:
         w = csv.writer(csvfile)
         w.writerow(headers)
         for row in results:
             w.writerow(row)
