import unicodecsv

headers = ['county', 'office', 'district', 'party', 'candidate', 'votes', 'winner', 'write-in', 'notes']
counties = ['Apache','Cochise','Coconino','Gila','Graham','Greenlee','La Paz','Maricopa','Mohave','Navajo','Pima','Pinal','Santa Cruz','Yavapai','Yuma','']
cds = ['U.S. House 1', 'U.S. House 2', 'U.S. House 3', 'U.S. House 4', 'U.S. House 5', 'U.S. House 6', 'U.S. House 7', 'U.S. House 8', '']
offices = ['PRESIDENT OF THE UNITED STATES', 'U.S. Senate', 'U.S. REPRESENTATIVE IN CONGRESS', 'GOVERNOR', 'STATE SENATOR', 'STATE REPRESENTATIVE', 'SECRETARY OF STATE', 'ATTORNEY GENERAL', 'STATE TREASURER', 'SUPERINTENDENT OF PUBLIC INSTRUCTION', 'STATE MINE INSPECTOR', 'CORPORATION COMMISSIONER', 'CORPORATION COMMISSION', 'PRESIDENTIAL ELECTORS']
office_lookup = {
    'U.S. Senate' : 'U.S. Senate', 'U.S. REPRESENTATIVE IN CONGRESS' : 'U.S. House', 'GOVERNOR' : 'Governor', 'STATE SENATOR' : 'State Senate',
    'STATE REPRESENTATIVE' : 'State Representative', 'SECRETARY OF STATE' : 'Secretary of State', 'ATTORNEY GENERAL' : 'Attorney General',
    'STATE TREASURER' : 'State Treasurer', 'SUPERINTENDENT OF PUBLIC INSTRUCTION' : 'Superintendent of Public Instruction',
    'STATE MINE INSPECTOR' : 'State Mine Inspector', 'CORPORATION COMMISSIONER' : 'Corporation Commissioner', 'PRESIDENT OF THE UNITED STATES' : 'President',
    'CORPORATION COMMISSION' : 'Corporation Commissioner', 'PRESIDENTIAL ELECTORS' : 'President'
}

with open('20040203__az__primary__president.csv', 'wb') as csvfile:
    w = unicodecsv.writer(csvfile, encoding='utf-8')
    w.writerow(headers)

    lines = open('/Users/derekwillis/Downloads/Canvass2004PPE.txt').readlines()

    for line in lines:
        party = None
        write_in = None
        notes = None
        if line == '\n':
            continue
        if len([x for x in offices if x in line]) > 0:
            office = [x for x in offices if x in line][0]
            if 'DISTRICT' in line:
                office, district = line.strip().split(' - ')
                district = district.replace('DISTRICT NO. ','')
            else:
                district = None
            display_office = office_lookup[office]
            if 'TERM EXPIRING' in office:
                notes = line.strip().split(' - ')[1]
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
                if '*' in candidate_bits and county == '':
                    race_winner = True
                else:
                    race_winner = None
                if 'Deceased' in name:
                    name = name.replace('(Deceased', '')
                    notes = 'Deceased'
                if 'Withdrew' in name:
                    name = name.replace('(Withdrew', '')
                    notes = 'Withdrew'
                name = name.replace('*','').strip()
                w.writerow([county, display_office, district, party, name, int(votes.strip()), race_winner, write_in, notes])
