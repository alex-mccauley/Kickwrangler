import pymysql as mdb
import pickle
import pandas as pd
import re
import sys

class create_database:

	def __init__(self):
		self.con = mdb.connect(host='localhost', user='root', passwd='', db='kickstarterdb', autocommit=True, charset='utf8')

		# compiled regex for string cleaning - remove all non alpha-numeric (and whitespace) characeters
		self.regex = re.compile('[^a-zA-Z0-9?!., ]')

	## Helper methods
	def _show_tables(self):
		return self._execute_sql("SHOW TABLES")

	def _fetch_counts(self, table_name):
		return self._execute_sql("SELECT COUNT(*) FROM %s" % table_name)

	def _clean_comment(self,text):
		return self.regex.sub(' ',text)

	# simple SQL interface for one-off commands
	def _execute_sql(self, sql_string):
		cur = self.con.cursor(mdb.cursors.DictCursor)
		cur.execute(sql_string)
		return cur.fetchall()

	def _create_projects_table(self, filename, status=0, append=False):
		# status = 0 means successful, = 1 means live
		# load tech projects
		# tech_projects = pickle.load(open('data/2015_06_04_tech_projects.p','rb'))
		tech_projects = pickle.load(open(filename,'rb'))

		# convert to dataframe
		k = []
		pledged = []
		goal = []
		backer_count = []
		category = []
		urls = []
		titles = []

		for key in tech_projects:
		    proj = tech_projects[key]
		    k.append(key)
		    pledged.append(proj['pledged'])
		    goal.append(proj['goal'])
		    category.append(proj['category']['slug'])
		    titles.append(proj['slug'])
		    backer_count.append(proj['backers_count'])
		    urls.append(proj['urls']['web']['project'].encode("ascii","ignore"))
		            
		proj_data = pd.DataFrame()
		proj_data['project_id']=k
		proj_data['pledged']=pledged
		proj_data['backer_count']=backer_count
		proj_data['category']=category
		proj_data['url'] = urls
		proj_data['project_title'] = titles
		proj_data['goal'] = goal

		cur = self.con.cursor()

		if not append: # clean away existing table
			cur.execute("DROP TABLE IF EXISTS projects")
			cur.execute("CREATE TABLE projects (project_id int, pledged int, goal int, backer_count int, category VARCHAR(255), url VARCHAR(1024), status int);")

		print 'number of rows = %d' % len(proj_data.index)
		for ii in proj_data.index:
			row = proj_data.iloc[ii]
			str_pre = "INSERT INTO projects (project_id, pledged, goal, backer_count, category, url, status) " 
			str_values = "VALUES (%d, %d, %d, %d, '%s', '%s', %d);" % (row['project_id'], row['pledged'], row['goal'], row['backer_count'], row['category'], row['url'], status)
			cur.execute(str_pre + str_values)

	def _create_probabilities_table(self, filename, append=False):
		# predicted probability of success per project (by project_id)
		project_df = pickle.load(open(filename, 'rb'))

		cur = self.con.cursor()

		if not append: # clean away existing table
			cur.execute("DROP TABLE IF EXISTS success_probs")
			cur.execute("CREATE TABLE success_probs (project_id int, pledged FLOAT, goal FLOAT, success_prob FLOAT);")

		for ii in project_df.index:
			row = project_df.iloc[ii]
			str_pre = "INSERT INTO success_probs (project_id, pledged, goal, success_prob) "
			str_values ="VALUES (%d, %f, %f, %f);" % (row['project_id'], row['pledged'], row['goal'], row['success_prob'])
			cur.execute(str_pre + str_values)

	def create_sentiments_table(self, filename, append=False):

		cur = self.con.cursor()
		if not append: # clean away existing table
			cur.execute("DROP TABLE IF EXISTS sentiments")
			cur.execute("CREATE TABLE sentiments (project_id int, date_from_start FLOAT, sentiment FLOAT, date_unit VARCHAR(24));")

		sentiment_df = pickle.load(open(filename, 'rb'))
		time_unit_string = "M"
		time_unit = pd.tslib.Timedelta(1,time_unit_string) # store in units of months
		# drop sentiments with weird dates
		eoy = pd.Timestamp('2015-12-30 00:00:00')
		sentiment_df = sentiment_df[sentiment_df['date'] < eoy]		
		sentiment_df['date_from_start_norm'] = sentiment_df['date_from_start'] / time_unit

		for ii in range(len(sentiment_df)):
			row = sentiment_df.iloc[ii]
			str_pre = "INSERT INTO sentiments (project_id, date_from_start, sentiment, date_unit) "
			str_values = "VALUES (%d, %f, %f, '%s');" % (row['project_id'], row['date_from_start_norm'], row['sentiment'], time_unit_string)
			cur.execute(str_pre + str_values)			

	def _create_comments_table(self):
		# dict of dataframes
		comment_data = pickle.load(open('data/sentiment_data_06_08.p','rb'))

		cur = self.con.cursor()

		# CHARACTER SET = utf8mb4
		cur.execute("DROP TABLE IF EXISTS comments") # TODO: add user_id
		cur.execute("Create TABLE comments (project_id int, comment_id int, date DATE, text VARCHAR(10000) CHARACTER SET utf8mb4)")

		for ii in comment_data['data'].index:
			if ii % 10000 == 0:
				print 'running row %d of %d' % (ii, len(comment_data['data']))
				sys.stdout.flush()
			
			row = comment_data['data'].iloc[ii]
			comment = self._clean_comment(row['text'])

			# cut comment length
			max_length = 9999
			comment = comment[:max_length]

			str_pre = "INSERT INTO comments (project_id, comment_id, date, text) "
			str_values = "VALUES (%d, %d, '%s', '%s');" % (row['keys'], row['idx'], str(row['dates'].date()), comment)
			cur.execute(str_pre + str_values)

	def _create_funding_goal_table(self):
		goal_data = pickle.load(open('data/campaign_goal_data_06_09.p','rb'))

		cur = self.con.cursor()

		cur.execute("DROP TABLE IF EXISTS funding_goal")
		cur.execute("CREATE TABLE funding_goal (project_id int, funding_goal int);")

		for ii in goal_data.index:
			row = goal_data.iloc[ii]
			str_pre = "INSERT INTO funding_goal (project_id, funding_goal) "
			str_values = "VALUES (%d, %d);" % (row['keys'], row['funding_goal'])
			cur.execute(str_pre + str_values)

	def _create_simple_sentiment_table(self):
		data = pickle.load(open('data/comments_data_processed.p','rb'))
		df_sentiments = data['sentiments']

		cur = self.con.cursor()

		cur.execute("DROP TABLE IF EXISTS sentiments_simple")
		cur.execute("CREATE TABLE sentiments_simple (project_id int, comment_id int, word_count int, sentiment int);")

		for row_tup in df_sentiments.iterrows():
			row = row_tup[1]
			str_pre = "INSERT INTO sentiments_simple (project_id, comment_id, word_count, sentiment) "			
			str_values = "VALUES (%d, %d, %d, %d);" % (int(row['project_id']), int(row['comment_id']), int(row['word_count']), int(row['sentiment']))
			cur.execute(str_pre + str_values)




