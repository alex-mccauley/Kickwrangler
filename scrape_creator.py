from __future__ import division
import pickle
import requests
import json
import re
from bs4 import BeautifulSoup
import time
import numpy as np
import pandas as pd
import sys

# Scrapes for creator data and returns a dataframe
def scrape_creator_data(project_data):
	# Input: dict keyed on project_id, containing basic project data

	creator_keys = []
	creator_backed = []
	creator_created = []
	creator_comments = []

	count = len(creator_keys)
	for key in project_data:
		if key not in creator_keys:
			try:
				url = project_data[key]['creator']['urls']['web']['user']
				r = requests.get(url).text
				soup = BeautifulSoup(r)

				s = soup.find_all(id='project_nav')[0].text
				s_rep = s.replace('\n','')
				backed = int(re.search('Backed(.+?)Created', s_rep).group(1).strip('()').replace(',',''))
				created = int(re.search('Created(.+?)Comments', s_rep).group(1).strip('()').replace(',',''))
				comments = int(re.search('Comments\n(.+?)\n', s).group(1).strip('()').replace(',',''))

				creator_keys.append(key)
				creator_backed.append(backed)
				creator_created.append(created)
				creator_comments.append(comments)

				time.sleep(0.1)

				if count % 100 == 0:
					print 'Step %d of %d' % (count, len(project_data.keys()))
			except IndexError:
				print 'Could not find index for key %d' % key
				continue
			count = count + 1

	# read into dataframe
	df = pd.DataFrame()
	df['project_id'] = creator_keys
	df['projects_backed'] = creator_backed
	df['creator_created'] = creator_created
	df['creator_comments'] = creator_comments

	return df

def scrape_goal_data(project_data):
	count = 0
	goals = []
	keys = []
	for key in project_data:
		if key not in keys:
			url = project_data[key]['urls']['web']['project']
			url_campaign = url.replace('?ref=discovery','/description')

			try:
				r = requests.get(url_campaign)#, verify=False) # avoid SSLError
				txt = re.search('<span class="money usd no-code">(.+?)</span> goal\n', r.text).group(1)
				goal = np.float(txt.strip('$').replace(',',''))
			# this will fail for non USD pledges
			except AttributeError:
				print "Failed at key %d" % key
				goal = None

			if goal is not None:
				keys.append(key)
				goals.append(goal)

			time.sleep(0.1) # avoid upsetting server
			count = count + 1
			if count % 100 == 0:
				print "Finished key %d of %d" % (count, len(project_data.keys()))

	# construct dataframe
	df = pd.DataFrame()
	df['project_id'] = keys
	df['funding_goal'] = goals
	return df

def run_goal():
	# games projects
	inputfile = 'data/projects_games_2015_06_10.p'
	outputfile = 'data/goal_data_games_06_12.p'

	inputdata = pickle.load(open(inputfile,'rb'))
	goal_df = scrape_goal_data(inputdata)
	print "Successfully scraped goal data"
	pickle.dump(goal_df, open(outputfile, 'wb'))

def run_creator(inputfile, outputfile):
	# games projects
#	inputfile = 'data/projects_games_2015_06_10.p'
#	outputfile = 'data/creator_data_games_06_12.p'

	inputdata = pickle.load(open(inputfile,'rb'))
	creator_df = scrape_creator_data(inputdata)
	print "Successfully scraped creator data"
	pickle.dump(creator_df, open(outputfile, 'wb'))
