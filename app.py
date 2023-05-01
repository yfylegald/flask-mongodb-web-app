#!/usr/bin/env python3

from flask import Flask, render_template, request, redirect, url_for, make_response
from markupsafe import escape
import pymongo
import datetime
from bson.objectid import ObjectId
import os
import subprocess

# instantiate the app
app = Flask(__name__)

# load credentials and configuration options from .env file
# if you do not yet have a file named .env, make one based on the template in env.example
import credentials
config = credentials.get()

# turn on debugging if in development mode
if config['FLASK_ENV'] == 'development':
    # turn on debugging, if in development
    app.debug = True # debug mnode

# make one persistent connection to the database
connection = pymongo.MongoClient(config['MONGO_HOST'], 27017,
                                username=config['MONGO_USER'],
                                password=config['MONGO_PASSWORD'],
                                authSource=config['MONGO_DBNAME'])
db = connection[config['MONGO_DBNAME']] # store a reference to the database

# set up the routes

@app.route('/')
def home():
    """
    Route for the home page
    """
    return render_template('index.html')


@app.route('/movie_list')
def movie_list():
    """
    Route for GET requests to the movie list page.
    Displays some information for the user with links to other pages.
    """
    docs = db.movie.find({}).sort("created_at", -1) # sort in descending order of created_at timestamp
    return render_template('movie_list.html', docs=docs) # render the read template


@app.route('/add')
def add():
    """
    Route for GET requests to the add a movie page.
    Displays a form users can fill out to create a new document.
    """
    category_list = list(db.category.find({}, {"name":1, "_id": 0}).sort("name", 1))
    if len(category_list) == 0:
        category_list = ['Action', 'Comedy', 'Crime', 'Horror', 'Romance']
        db.category.insert_many([{'name': c} for c in category_list])
    else:
        category_list = [c['name'] for c in category_list]
    data = {'title': '', 'director': '', 'rating': '', 'category': '', 'description': ''}
    return render_template('add.html', category_list = category_list, data = data) # render the add a movie template

def get_user_input(is_update = False):
    """
    Return user input data in the form, return error message if has error.
    """
    title = request.form['ftitle']
    director = request.form['fdirector']
    rating = request.form['frating']
    category = request.form['fcategory']
    description = request.form['fdescription']
    category_list = list(db.category.find({}, {"name":1, "_id": 0}).sort("name", 1))
    category_list = [c['name'] for c in category_list]
    data = {'title': title, 'director': director, 'rating': rating, 'category': category, 'description': description, "created_at": datetime.datetime.now()}
    if len(title) == 0:
        return category_list, data, "Please enter title"
    #check if duplicate title
    if not is_update and db.movie.find_one({"title": title}) != None:
        return category_list, data, "This movie is exists!"
    if len(director) == 0:
        return category_list, data, "Please enter director"
    try:
        rating = float(rating)
    except:
        rating = -1
    if not (rating >= 0 and rating <= 10):
        return category_list, data, "Please enter rating between 1 and 10"
    return category_list, data, None

@app.route('/add', methods=['POST'])
def add_movie():
    """
    Route for POST requests to the create page.
    Accepts the form submission data for a new document and saves the document to the database.
    """
    category_list, data, message = get_user_input()
    if message != None:
        return render_template('add.html', category_list = category_list, error_message = message, data = data)
    # create a new document with the data the user entered
    db.movie.insert_one(data) # insert a new document
    return redirect(url_for('movie_list')) # tell the browser to make a request for the /movie_list route

@app.route('/edit/<mongoid>')
def edit(mongoid):
    """
    Route for GET requests to the edit page.
    Displays a form users can fill out to edit an existing record.
    """
    data = db.movie.find_one({"_id": ObjectId(mongoid)})
    category_list = list(db.category.find({}, {"name":1, "_id": 0}).sort("name", 1))
    category_list = [c['name'] for c in category_list]
    return render_template('edit.html', mongoid=mongoid, category_list = category_list, data=data) # render the edit template


@app.route('/edit/<mongoid>', methods=['POST'])
def edit_movie(mongoid):
    """
    Route for POST requests to the edit page.
    Accepts the form submission data for the specified document and updates the document in the database.
    """
    category_list, data, message = get_user_input(is_update = True)
    # display error message if has error input data
    if message != None:
        return render_template('edit.html', mongoid=mongoid, category_list = category_list, data=data, error_message = message) # render the edit template

    db.movie.update_one(
        {"_id": ObjectId(mongoid)}, # match criteria
        { "$set": data }
    )

    return redirect(url_for('movie_list')) # tell the browser to make a request for the /movie_list route


@app.route('/delete/<mongoid>')
def delete(mongoid):
    """
    Route for GET requests to the delete page.
    Deletes the specified record from the database, and then redirects the browser to the read page.
    """
    db.movie.delete_one({"_id": ObjectId(mongoid)})
    return redirect(url_for('movie_list')) # tell the web browser to make a request for the /movie_list route.

@app.route('/top10')
def top10():
    docs = db.movie.find({}).sort("rating", -1).limit(3) # sort in descending order of created_at timestamp
    return render_template('top3_list.html', docs=docs) # render the read template

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    GitHub can be configured such that each time a push is made to a repository, GitHub will make a request to a particular web URL... this is called a webhook.
    This function is set up such that if the /webhook route is requested, Python will execute a git pull command from the command line to update this app's codebase.
    You will need to configure your own repository to have a webhook that requests this route in GitHub's settings.
    Note that this webhook does do any verification that the request is coming from GitHub... this should be added in a production environment.
    """
    # run a git pull command
    process = subprocess.Popen(["git", "pull"], stdout=subprocess.PIPE)
    pull_output = process.communicate()[0]
    # pull_output = str(pull_output).strip() # remove whitespace
    process = subprocess.Popen(["chmod", "a+x", "flask.cgi"], stdout=subprocess.PIPE)
    chmod_output = process.communicate()[0]
    # send a success response
    response = make_response('output: {}'.format(pull_output), 200)
    response.mimetype = "text/plain"
    return response

@app.errorhandler(Exception)
def handle_error(e):
    """
    Output any errors - good for debugging.
    """
    return render_template('error.html', error=e) # render the edit template


if __name__ == "__main__":
    #import logging
    #logging.basicConfig(filename='/home/ak8257/error.log',level=logging.DEBUG)
    app.run(debug = True)

