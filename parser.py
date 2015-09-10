import unicodecsv

headers = ['county', 'office', 'district', 'party', 'candidate', 'votes', 'winner', 'write-in']
counties = ['Apache','Cochise','Coconino','Gila','Graham','Greenlee','La Paz','Maricopa','Mohave','Navajo','Pima','Pinal','Santa Cruz','Yavapai','Yuma','']
offices = ['U.S. SENATOR', 'U.S. REPRESENTATIVE IN CONGRESS', 'GOVERNOR', 'STATE SENATOR', 'STATE REPRESENTATIVE', 'SECRETARY OF STATE', 'ATTORNEY GENERAL', 'STATE TREASURER', 'SUPERINTENDENT OF PUBLIC INSTRUCTION', 'STATE MINE INSPECTOR', 'CORPORATION COMMISSIONER']
office_lookup = {
    'U.S. SENATOR' : 'U.S. Senate', 'U.S. REPRESENTATIVE IN CONGRESS' : 'U.S. House', 'GOVERNOR' : 'Governor', 'STATE SENATOR' : 'State Senate',
    'STATE REPRESENTATIVE' : 'State House', 'SECRETARY OF STATE' : 'Secretary of State', 'ATTORNEY GENERAL' : 'Attorney General',
    'STATE TREASURER' : 'State Treasurer', 'SUPERINTENDENT OF PUBLIC INSTRUCTION' : 'Superintendent of Public Instruction',
    'STATE MINE INSPECTOR' : 'State Mine Inspector', 'CORPORATION COMMISSIONER' : 'Corporation Commissioner'
}


with open('20100824__az__primary.csv', 'wb') as csvfile:
    w = unicodecsv.writer(csvfile, encoding='utf-8')
    w.writerow(headers)

    lines = open('Canvass2010PE.txt').readlines()

    for line in lines:
        party = None
        write_in = None
        if line == '\n':
            continue
        if len([x for x in offices if x in line]) == 1:
            office = [x for x in offices if x in line][0]
            if 'DISTRICT' in line:
                office, district = line.strip().split(' - ')
                district = district.replace('DISTRICT NO. ','')
            else:
                district = None
            display_office = office_lookup[office]
        else:
            bits = line.split('\t')
            candidate_bits = bits[0]
            party = candidate_bits.split(')')[0].strip().replace('(','')
            name = candidate_bits.split(')')[1].strip()
            if 'Write-In' in name:
                write_in = True
                name = name.split('(')[0].strip()
            results_bits = [(x.replace(',','')) for x in bits[1:]]
            county_results = zip(counties, results_bits)
            county_results = [(x,y) for (x,y) in county_results if y != '']
            for county, votes in county_results:
                if '*' in candidate_bits.split(')')[1].strip() and county == '':
                    race_winner = True
                else:
                    race_winner = None
                name = name.replace('*','').strip()
                w.writerow([county, display_office, district, party, name, int(votes.strip()), race_winner, write_in])
