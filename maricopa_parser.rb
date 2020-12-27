require 'remote_table'
require 'csv'

county = 'Maricopa'
t = RemoteTable.new("/Users/dwillis/code/openelections-sources-az/2020/Maricopa\ AZ\ ExportByPrecinct_110320.csv")
rows = t.entries
results = []
headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes', 'early_voting', 'election_day', 'provisional']

offices = {
  'Presidential Electors' => ['President', nil],
  'US Senate-Term Expires JANUARY 3, 2023' => ['U.S. Senate', nil],
  'US Rep Dist CD-1' => ['U.S. House', 1],
  'US Rep Dist CD-3' => ['U.S. House', 3],
  'US Rep Dist CD-4' => ['U.S. House', 4],
  'US Rep Dist CD-5' => ['U.S. House', 5],
  'US Rep Dist CD-6' => ['U.S. House', 6],
  'US Rep Dist CD-7' => ['U.S. House', 7],
  'US Rep Dist CD-8' => ['U.S. House', 8],
  'US Rep Dist CD-9' => ['U.S. House', 9],
  'State Senator Dist-1' => ['State Senate', 1],
  'State Senator Dist-4' => ['State Senate', 4],
  'State Senator Dist-12' => ['State Senate', 12],
  'State Senator Dist-13' => ['State Senate', 13],
  'State Senator Dist-15' => ['State Senate', 15],
  'State Senator Dist-16' => ['State Senate', 16],
  'State Senator Dist-17' => ['State Senate', 17],
  'State Senator Dist-18' => ['State Senate', 18],
  'State Senator Dist-19' => ['State Senate', 19],
  'State Senator Dist-20' => ['State Senate', 20],
  'State Senator Dist-21' => ['State Senate', 21],
  'State Senator Dist-22' => ['State Senate', 22],
  'State Senator Dist-23' => ['State Senate', 23],
  'State Senator Dist-24' => ['State Senate', 24],
  'State Senator Dist-25' => ['State Senate', 25],
  'State Senator Dist-26' => ['State Senate', 26],
  'State Senator Dist-27' => ['State Senate', 27],
  'State Senator Dist-28' => ['State Senate', 28],
  'State Senator Dist-29' => ['State Senate', 29],
  'State Senator Dist-30' => ['State Senate', 30],
  'State Rep Dist-1' => ['State House', 1],
  'State Rep Dist-4' => ['State House', 4],
  'State Rep Dist-12' => ['State House', 12],
  'State Rep Dist-13' => ['State House', 13],
  'State Rep Dist-15' => ['State House', 15],
  'State Rep Dist-16' => ['State House', 16],
  'State Rep Dist-17' => ['State House', 17],
  'State Rep Dist-18' => ['State House', 18],
  'State Rep Dist-19' => ['State House', 19],
  'State Rep Dist-20' => ['State House', 20],
  'State Rep Dist-21' => ['State House', 21],
  'State Rep Dist-22' => ['State House', 22],
  'State Rep Dist-23' => ['State House', 23],
  'State Rep Dist-24' => ['State House', 24],
  'State Rep Dist-25' => ['State House', 25],
  'State Rep Dist-26' => ['State House', 26],
  'State Rep Dist-27' => ['State House', 27],
  'State Rep Dist-28' => ['State House', 28],
  'State Rep Dist-29' => ['State House', 29],
  'State Rep Dist-30' => ['State House', 30]
}

rows.each do |row|
  if offices.keys.include? row['ContestName']
    office, district = offices[row['ContestName']]
  else
    office = row['ContestName']
    district = nil
  end
  if row['ContestName'] == 'Presidential Electors' and row['CandidateId'] == '1'
    results << [county, row['PrecinctName'], office, district, nil, 'Over Votes', row['Overvotes'], row['Overvotes_EARLY VOTE'], row['Overvotes_ELECTION DAY'], row['Overvotes_PROVISIONAL']]
    results << [county, row['PrecinctName'], office, district, nil, 'Under Votes', row['Undervotes'], row['Undervotes_EARLY VOTE'], row['Undervotes_ELECTION DAY'], row['Undervotes_PROVISIONAL']]
    results << [county, row['PrecinctName'], 'Registered Voters', nil, nil, nil, row['Registered'], nil, nil, nil]
    results << [county, row['PrecinctName'], 'Ballots Cast', nil, nil, nil, row['Turnout'], row['Turnout_EARLY VOTE'], row['Turnout_ELECTION DAY'], row['Turnout_PROVISIONAL']]
  end
  results << [county, row['PrecinctName'], office, district, row['CandidateAffiliation'], row['CandidateName'], row['Votes'], row['Votes_EARLY VOTE'], row['Votes_ELECTION DAY'], row['Votes_PROVISIONAL']]
#  if row['candidate_id'] == "1"
#    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Over Votes', row['total_over_votes'], row['early_over_votes'], row['election_over_votes'], row['absentee_over_votes']]
#    results << [county, row['Precinct_name'], office, district, row['Party_Code'], 'Under Votes', row['total_under_votes'], row['early_under_votes'], row['election_under_votes'], row['absentee_under_votes']]
#  end
end

CSV.open("20201103__az__general__#{county.downcase.gsub(' ','_')}__precinct.csv", "w") do |csv|
  csv << headers
  results.map{|r| csv << r}
end
