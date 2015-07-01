from __future__ import division
import numpy as np
import pandas as pd

# text processing helper functions
def strip_url(url):
    # remove last ? component, as this relates to how the project page was found
    url_split = url.split('?') 
    return '?'.join(url_split[:-1])

def process_query_by_url(cur, project_url):
    cleaned_url = strip_url(project_url)

    sql_string = "SELECT * FROM projects WHERE url LIKE '%s%%';" % cleaned_url
    #print sql_string
    cur.execute(sql_string)    
    project_data = cur.fetchall()

    return project_data

def process_query_by_id(cur, project_id):

	# select project
    cur.execute("SELECT * FROM projects WHERE project_id=%d;" % int(project_id))
    project_data = cur.fetchall()

    # join comments and sentiments for this project
    join_str = "SELECT * FROM comments INNER JOIN sentiments_simple USING (project_id, comment_id) WHERE project_id=%s" % project_id
    cur.execute(join_str)
    comment_data = cur.fetchall()

    # convert to dataframe
    df = pd.DataFrame(columns=['project_id', 'comment_id', 'date', 'text', 'word_count', 'sentiment'])
    for ii, r in enumerate(comment_data):
    	df.loc[ii] = [r['project_id'], r['comment_id'], r['date'], r['text'], r['word_count'], r['sentiment']]

    # returns list of dicts
    return df

def compute_project_sentiment(df):

	# assume only one project present
	if len(np.unique(df['project_id'])) > 1:
		raise ValueError("More than one project key is present")
			

	# filter out comments before the past 6 months of the last comment and after first 2 months
	time_window = pd.tslib.Timedelta(value=60,unit='D')
	min_duration = pd.tslib.Timedelta(value=150,unit='D')

	last_time = df['date'].max()
	first_time = df['date'].min()

	df_filtered = df[df['date'] > last_time - time_window]
	df_filtered = df_filtered[df_filtered['date'] > first_time + min_duration]

	if len(df_filtered) == 0:
		#return None, None, None, None
		# TEMP turn off filtering:
		df_filtered = df

	# threshold sentiments
	sents_pos = len(df_filtered[df_filtered['sentiment'] > 0])
	sents_neg = len(df_filtered[df_filtered['sentiment'] < 0])
	total_comments = len(df_filtered)

	# compute average sentiment and negative fraction
	average_sentiment = (sents_pos + sents_neg) / total_comments
	negative_fraction = sents_neg / (sents_neg + sents_pos + 1)

	# find most expressive comments
	df_filtered['expression'] = df_filtered['sentiment'] / df_filtered['word_count']
	df_filtered.sort(columns='expression', ascending=True) # most negative first

	## TODO: catch case with < 4 comments
	top_negative = df_filtered[:2]
	top_positive = df_filtered[-2:]

	return average_sentiment, negative_fraction, top_negative, top_positive

def compute_sentiment_time_series(df):
	#dates = df['dates']
	#x = np.linspace(0, 1, len(dates))

	return 1,2



