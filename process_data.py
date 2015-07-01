from __future__ import division
import pickle
import numpy as np
import pandas as pd
import nltk
from nltk import word_tokenize
from dateutil import parser

# Read in (tech) comments and process, save to output file

stemmer = nltk.stem.porter.PorterStemmer()

# add complaint, attorney general 
# 6/15: removed "wait"
good_words = map(stemmer.stem, ['great', 'cool', 'fast', 'awesome', 'excited', 'shipped', 'arrived', 'received'])
bad_words = map(stemmer.stem, ['delay','worst','awful', 'bad', 'fraud','dead','shame','cancel', 'wtf','unprofessional','mistake', 'fucking','sorry','rude'])
very_bad_words = map(stemmer.stem, ['complaint', 'refund', 'cancel', 'fraud', 'scam', 'stole'])

def convert_project_dict_to_dataframe(project_dict):
	project_ids = []
	backers = []
	pledged = []
	goal = []
	category_id = []
	category_name = []
	urls = []
	creator_id = []

	for project_id in project_dict:
		proj = project_dict[project_id]

		project_ids.append(project_id)
		backers.append(proj['backers_count'])
		pledged.append(proj['pledged'])
		goal.append(proj['goal'])
		category_id.append(proj['category']['id'])
		category_name.append(proj['category']['slug'])
		urls.append(proj['urls']['web']['project'])

		# you get to the creator's website by https://www.kickstarter.com/profile/[id]
		creator_id.append(proj['creator']['id'])

	df = pd.DataFrame()
	df['project_id'] = project_ids
	df['backers'] = backers
	df['pledged'] = pledged
	df['goal'] = goal
	df['category_id'] = category_id
	df['category_name'] = category_name
	df['urls'] = urls
	df['creator_id'] = creator_id

	return df

def convert_dict_to_dataframe(comments_dict):
	keys = []
	comments_index = []
	dates = []
	comments = []
	users = []

	for key in comments_dict:
		for key_c in comments_dict[key]:
			if type(key_c) is not int:
				continue

			proj = comments_dict[key]
			# attempt to parse date
			try:
				date = parser.parse(proj[key_c]['date'])
			except ValueError:
				# try nearest neighbors
				try:
					date = parser.parse(proj[key_c-1]['date'])
				except (KeyError, ValueError):
					try:
						date = parser.parse(proj[key_c+1]['date'])
					except (KeyError, ValueError):
						date = None # cannot extract date

			comment = proj[key_c]['comment']
			user = proj[key_c]['user']

			if date is not None and len(comment) > 0: # drop empties
				keys.append(key)
				comments_index.append(key_c)
				comments.append(comment)
				dates.append(date)
				users.append(user)

	df = pd.DataFrame()
	df['project_id'] = keys
	df['comment_id'] = comments_index
	df['comment'] = comments
	df['date'] = dates
	df['user'] = users

	return df

def get_comment_sentiment_simple(comment, stemmer):
	if len(comment) < 1:	
		return 0
	
	tokenized = word_tokenize(comment.lower())
	stemmed = map(stemmer.stem, tokenized)
	word_count = len(stemmed)

	# simple: count positives and negatives
	count = 0
	very_bad_count = 100
	for word in stemmed:
		if word in good_words:
			count = count + 1
		if word in bad_words:
			count = count - 1
		if word in very_bad_words:
			very_bad_count = -1
	return min([count, very_bad_count]), word_count
    
def compute_sentiments(comments_dict):
	stemmer = nltk.stem.porter.PorterStemmer()

	n_keys = len(comments_dict.keys())
	count = 0

	project_ids = []
	comment_ids = []
	sentiments = []
	word_counts = []
	for key in comments_dict:
		count = count + 1
		if count % int(round(n_keys/10)) == 0:
			print '%d percent complete' % int(100 * count / n_keys)

		for key_c in comments_dict[key]:
			comment = comments_dict[key][key_c]['comment']
			if len(comment) == 0:
				s = 0 # neutral
				word_count = 1
			else:
				s, word_count = get_comment_sentiment_simple(comment, stemmer)

			project_ids.append(key)
			comment_ids.append(key_c)
			sentiments.append(s)
			word_counts.append(word_count)
	df = pd.DataFrame()
	df['project_id'] = project_ids
	df['comment_id'] = comment_ids
	df['sentiment'] = sentiments
	df['word_count'] = word_counts
	df.dropna(axis=0)
	return df

def process_data(comments_dict):
	comments_df = convert_dict_to_dataframe(comments_dict)
	sentiments_df = compute_sentiments(comments_dict)

	# add in duration to project data df
	return [comments_df, sentiments_df]		

def prepare_project_data(project_dict_fname, creator_df_fname):
	# convert data
	project_dict = pickle.load(open(project_dict_fname,'rb'))
	project_df = convert_project_dict_to_dataframe(project_dict)

	creator_data = pickle.load(open(creator_df_fname, 'rb'))
	creator_data.rename(columns={'keys':'project_id', 'number_backed':'projects_backed','number_created':'creator_created', 'number_comments':'creator_comments'},inplace=True)

	creator_df_features = creator_data.copy(deep=True)
	for feat in ['projects_backed', 'creator_created', 'creator_comments']:
	    creator_df_features[feat] = creator_df_features[feat].apply(lambda x: np.log(x+1))
	creator_df_features.rename(columns={'projects_backed':'log_backed','creator_created':'log_created','creator_comments':'log_comments'},inplace=True)

	project_df_features = project_df.copy(deep=True)
	for feat in ['backers', 'pledged', 'goal']:
	    project_df_features[feat] = project_df_features[feat].apply(lambda x: np.log(x+1))
	project_df_features.rename(columns={'backers':'log_backers','pledged':'log_pledged','goal':'log_goal'},inplace=True)
	project_df_features.drop(axis=1,labels=['creator_id','urls','category_id'],inplace=True)

	d = [{'category_name':x} for x in project_df_features['category_name'].values]

	from sklearn.feature_extraction import DictVectorizer
	vec = DictVectorizer()
	category_features = vec.fit_transform(d).toarray()

	project_df_features_cat = project_df_features.copy(deep=True)

	for ii, feat in enumerate(vec.feature_names_):
	    project_df_features_cat[feat.split('=')[-1]] = category_features[:,ii]
	project_df_features_cat.drop(axis=1,labels='category_name',inplace=True)

	project_creator_df_features = pd.merge(creator_df_features, project_df_features_cat,on='project_id',how='inner')
	means = project_creator_df_features.mean(axis=0)
	std = project_creator_df_features.std(axis=0)

	# returned mean/std are Series objects
	return project_creator_df_features, means, std


def run():
	# tech projects
	#inputfile = 'data/2015_06_06_comments_db.p'
	#outputfile = 'data/comments_data_processed_tech.p'

	# game projects
	inputfile = 'data/2015_06_10_game_comments_db.p'
	outputfile = 'data/comments_data_processed_games_v2_6_15.p'

	print "Computing data from %s, outputting to %s" %(inputfile,outputfile)
	comments_dict = pickle.load(open(inputfile,'rb'))
	[comments_df, sentiments_df] = process_data(comments_dict)
	# save output
	pickle.dump({'comments':comments_df,'sentiments':sentiments_df}, open(outputfile,'wb'))