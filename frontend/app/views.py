from flask import render_template, request 
from app import app
import pymysql as mdb
import process_query
import numpy as np
import pandas as pd
import json

db = mdb.connect(user="root", host="localhost", db="kickstarterdb",
	charset='utf8', autocommit=True)

@app.route('/slides')
def get_slides():
  return app.send_static_file('slides.html')
@app.route('/topics')
def get_topics():
  return app.send_static_file('topics.html')

@app.route('/')
@app.route('/index')
@app.route('/input')
def cities_input():
	return render_template("input.html")

def get_past_project_output(project_data):

  with db:

    cur = db.cursor(mdb.cursors.DictCursor)

    # get time series of sentiments
    sql_str = "SELECT * FROM sentiments WHERE project_id=%d;" % project_data['project_id']
    cur.execute(sql_str)
    results = cur.fetchall()

    # create time series of sentiments
    times = []
    sentiments = []
    for row in results:
      times.append(row['date_from_start'])
      sentiments.append(row['sentiment'])

    df = pd.DataFrame()
    df['times'] = times
    df['sentiments'] = sentiments
    df.sort('times', ascending=True, inplace=True)

  return render_template("output_past.html")

@app.route('/output')
def output():
  #pull 'url' from input field on submit and store it
  project_url = request.args.get('url')

  if len(project_url) == 0:
    # redirect back to input page - TODO: add error message
    return render_template("input.html", message="No results returned, please enter a valid URL")

  with db:

    # fetch project based on URL
    cur = db.cursor(mdb.cursors.DictCursor)
    project_data_list = process_query.process_query_by_url(cur, project_url)
    
    if type(project_data_list) is not list:
      return render_template("input.html")
    if len(project_data_list) == 0:
      return render_template("input.html", message="No results returned, please enter a valid URL")
    if len(project_data_list) > 1:
      # more than one matching URL
      return render_template("input.html", message="Multiple results returned, please enter a specific URL")

    project_data = project_data_list[0]

    ######## get data for all projects in this category
    category = project_data['category']
    # get average chance of success over all live projects
    cur.execute("SELECT AVG(success_prob) FROM success_probs;")
    avg_prob = cur.fetchall()[0].values()[0]

    # get average chance of success within this category
    sql_str = "SELECT AVG(success_prob) FROM projects JOIN success_probs ON success_probs.project_id=projects.project_id WHERE projects.category='%s';" % project_data['category']
    cur.execute(sql_str)
    avg_prob_cat = cur.fetchall()[0].values()[0]

    # find top 3 "best" projects
    sql_str = "SELECT * FROM projects JOIN success_probs ON success_probs.project_id=projects.project_id WHERE projects.category='%s' ORDER BY success_prob DESC LIMIT 3;" % project_data['category']
    cur.execute(sql_str)
    best_projs = cur.fetchall()

    ######## Route depending on if this is a live or past project
    status = project_data['status']
    if status == 0: # past project - get sentiment over time
      sql_str = "SELECT date_from_start, sentiment FROM sentiments where project_id=%d;" % project_data['project_id']
      cur.execute(sql_str)
      sentiment_data = cur.fetchall()
      #print sentiment_data
    
      sentiments = ['Sentiment']
      x = ['x']

      for d in sentiment_data:
        x.append(int(round(d['date_from_start'])))
        sentiments.append(int(round(10*d['sentiment'])))

      string_dict = {'string':"Already funded", 'color':"green"}
      return render_template("output_sentiment.html", x=json.dumps(x),sentiments=json.dumps(sentiments),string_dict=string_dict, project_data=project_data, best_projs=best_projs, category=category)

    else: # live project    
      # define map between success interval
      risk_ranges = [0.25, 0.5, 0.75, 1.0] # 
      risk_string = ['highly risky', 'risky', 'ok', 'sure thing']
      risk_color = ['red', 'orange', 'yellow', 'green']

      # get project's chance of success
      sql_str = "SELECT success_prob FROM success_probs WHERE project_id=%d;" % project_data['project_id']
      cur.execute(sql_str)
      prob_list = cur.fetchall()
#      print prob_list

      success_prob = prob_list[0]['success_prob']

      # find index
      category_index = [ii for ii in range(len(risk_ranges)) if success_prob <= risk_ranges[ii]][0]
      string_dict = {'string':risk_string[category_index], 'color':risk_color[category_index]}      

  return render_template("output.html", string_dict=string_dict, project_data=project_data, best_projs=best_projs, category=category, success_prob=success_prob, avg_prob=avg_prob, avg_prob_cat=avg_prob_cat)
  
  