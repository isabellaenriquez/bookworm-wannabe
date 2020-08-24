"""
set FLASK_APP=application.py
set DATABASE_URL=postgres://pjerzdbvvktwar:7ba8dab340e514f5485af2c8de58260b103cd557b70e690f105796bad5282fa5@ec2-52-201-55-4.compute-1.amazonaws.com:5432/dbpo79e0aep8br

"""

import os

from flask import Flask, session, render_template, request, redirect, url_for, abort, flash, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from functools import wraps # for wrapping functions
import gc # for garbage collection
import requests # for api stuff
from get_key import key # goodreads key

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

#decorator; f is function wrapped around
def login_required(f):
    @wraps(f)
    def wrap_fn(*args, **kws):
        if 'logged_in' in session:
            return f(*args, **kws)
        else:
            flash('You have no authorization. Please login or signup for Bookworm Wannabe.', 'error')
            return redirect(url_for('index'))
    return wrap_fn

@app.route("/", methods=["GET", "POST"])
def index():
    session.clear()
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear() # make sure no one is logged in

    if request.method == "POST":
        if not request.form.get("username"): # didn't enter a username
            return render_template("login.html", alert="username")
        
        # check is username exists
        user = db.execute("SELECT * FROM users WHERE username = :username", {"username": request.form.get("username")}).fetchone()
        if user == None:
            return render_template("login.html", alert="none")
        
        if not request.form.get("password"): # didn't enter a password
            return render_template("login.html", alert="password")

        # check if password is correct
        if request.form.get("password") == user["password"]:
            session['user_id'] = user["id"]
            session['username'] = user["username"]
            session['logged_in'] = True
            return redirect(url_for('home'))
        else: 
            return render_template("login.html", alert="incorrect")
        
        

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    session.clear() # make sure no one is logged in

    if request.method == "POST":
        if not request.form.get("username"): # didn't enter a username
            return render_template("signup.html", alert="username")
        
        # check is username is unique
        notUnique = db.execute("SELECT * FROM users WHERE username = :username", {"username": request.form.get("username")}).fetchone()
        if notUnique:
            return render_template("signup.html", alert="not unique")
        
        if not request.form.get("password"): # didn't enter a password
            return render_template("signup.html", alert="password")
        
        # all fields good, add to user database
        db.execute("INSERT INTO users (username, password) VALUES (:username, :password)", \
            {"username": request.form.get("username"), "password": request.form.get("password")})
        
        db.commit()

        return render_template("login.html")
    else:
        return render_template("signup.html")
        

#home page
@app.route("/home", methods=["GET", "POST"])
@login_required
def home():
    #fetch current user's list of reviews
    query = db.execute("SELECT review, rating, title, author, year FROM reviews JOIN books ON books.id = reviews.book_id WHERE user_id = :user_id", {"user_id": session["user_id"]})
    review_count = query.rowcount
    user_reviews = query.fetchall()
    return render_template("home.html", username=session["username"], reviews=user_reviews, review_count=review_count)

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    gc.collect() # garbage collection
    return render_template("index.html")

@app.route("/search-results", methods=["GET"])
@login_required
def search():
    #if request.method == "POST":
    string = request.args["search"]
    query = "%" + str(string) + "%"
    results = db.execute("SELECT * FROM books WHERE isbn LIKE :string OR title LIKE :string OR author LIKE :string", {"string": query})
    if results.rowcount == 0:
        message="No books found for \"" + str(string) + "\""
        return render_template("error.html", message=message)

    book_list = results.fetchall()
    return render_template("search.html", string=string, books=book_list)
    #return render_template("error.html", message="You are not authorized to see this page.")

@app.route("/details", methods=["GET", "POST"])
@login_required
def details():
    book = db.execute("SELECT * FROM books WHERE id = :id", {"id": request.args["book-id"]}).fetchone()
    reviews = db.execute("SELECT review, rating, username FROM reviews JOIN users ON reviews.user_id = users.id WHERE book_id = :book_id", {"book_id": book.id})
    bww_review_count = reviews.rowcount # bww reviews count only
    review_list = reviews.fetchall()

    # goodreads stuff
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": key, "isbns": book.isbn})
    info = res.json()
    gr_review_count = info['books'][0]['reviews_count']
    gr_avg_rating = info['books'][0]['average_rating']

    return render_template('details.html', reviews=review_list, review_count=bww_review_count, book=book, gr_review_count=gr_review_count, avg_rating=gr_avg_rating)

@app.route('/new-review', methods=["POST", "GET"])
@login_required
def write_review():
    if request.method == 'POST':
        db.execute('INSERT INTO reviews (user_id, book_id, review, rating) VALUES (:user_id, :book_id, :review, :rating)', {"user_id": session["user_id"], "book_id": request.form.get("book-id"), "review": request.form.get("message"), "rating": request.form.get("rating")})
        db.commit()
        return render_template('success.html')
    else:
        book = db.execute("SELECT * FROM books WHERE id = :id", {"id": request.args["book-id"]}).fetchone()
        # check if user wrote a review for book already
        wrote_review = db.execute("SELECT user_id FROM reviews WHERE book_id = :book_id AND user_id = :user_id", {"book_id": book.id, "user_id": session["user_id"]}).fetchone()
        if wrote_review is not None:
            return render_template("error.html", message="You already wrote a review for \"" + str(book.title) + "\".")
        return render_template('new-review.html', book=book)

@app.route('/api/<isbn>')
def api(isbn):
    book = db.execute('SELECT * FROM books WHERE isbn = :isbn', {'isbn': isbn}).fetchone()
    if book is not None:
        book_info = {"title": book.title, "author": book.author, "year": book.year, "isbn": isbn}
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": key, "isbns": book.isbn})
        info = res.json()
        book_info['review_count'] = info['books'][0]['reviews_count']
        book_info['avg_rating'] = info['books'][0]['average_rating']
        return jsonify(book_info)
    else:
        return render_template('404.html'), 404
