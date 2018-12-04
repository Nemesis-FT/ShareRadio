from flask import Flask, session, url_for, redirect, request, render_template, abort
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import os
import random
import string
import requests

app = Flask(__name__)
app.secret_key = "dacambiare"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Database tables go under here

class User(db.Model):
    uid = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, nullable=False, unique=True)
    password = db.Column(db.LargeBinary, nullable=False)
    isAdmin = db.Column(db.Boolean, nullable=False)
    songs = db.relationship("Song", back_populates="submitter")

    def __init__(self, username, password, type):
        self.username = username
        p = bytes(password, encoding="utf-8")
        self.password = bcrypt.hashpw(p, bcrypt.gensalt())
        self.isAdmin = type

    def __repr__(self):
        msg = ""
        if self.isAdmin:
            msg += "[ADMIN]"
        return msg + "{}-{}".format(self.uid, self.password)


class Song(db.Model):
    sid = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    playing = db.Column(db.String, nullable=False)
    submitter_id = db.Column(db.Integer, db.ForeignKey('user.uid'))
    submitter = db.relationship("User", back_populates="songs")

    def __init__(self, name, submitter_id):
        self.name = name
        self.submitter_id = submitter_id
        self.playing = False

    def __repr__(self):
        return "{}-{}".format(self.name, self.submitter_id)


# Website utility functions go under here


def login(username, password):  # Funzione di controllo credenziali
    user = User.query.filter_by(username=username).first()
    try:
        return bcrypt.checkpw(bytes(password, encoding="utf-8"), user.password)
    except AttributeError:
        # If user is non-existant
        return False


def find_user(username):  # Restituisce l'utente corrispondente all'username
    return User.query.filter_by(username=username).first()


# Website webpage functions go under here


@app.route("/")  # Website root, also used for logging off
def page_home():
    if 'username' not in session:
        return redirect(url_for('page_login'))
    else:
        session.pop('username')  # Logoff
        return redirect(url_for('page_login'))


@app.route("/login", methods=["GET", "POST"])  # Login page
def page_login():
    if request.method == "GET":
        return render_template("login.htm")
    else:
        if login(request.form['username'], request.form['password']):
            session['username'] = request.form['username']  # If both the username and the password are correct,
            return redirect(url_for('page_dashboard'))  # the user is appended to the session list.
        else:
            abort(403)


@app.route("/dashboard")
def page_dashboard():
    if 'username' not in session or 'username' is None:
        return redirect(url_for('page_login'))
    user = find_user(session['username'])
    currentSong = Song.query.filter_by(playing=True).first()
    songs = Song.query.filter_by(playing=False).limit(10).all()
    return render_template("/dashboard.htm", user=user, currentSong=currentSong, songs=songs)


@app.route("/add_user", methods=["GET", "POST"])
def page_user_add():
    if 'username' not in session or 'username' is None:
        return redirect(url_for('page_login'))
    user = find_user(session['username'])
    if not user.isAdmin:
        return abort(403)
    if request.method == "GET":
        return render_template("user/add.htm")
    else:
        newUser = User(request.form['username'], request.form['password'], 0)
        db.session.add(newUser)
        db.session.commit()
        return redirect(url_for('page_dashboard'))


@app.route("/addSong", methods=["POST"])
def api_song_add():
    if 'username' not in session or 'username' is None:
        return abort(403)
    user = find_user(session['username'])
    check = Song.query.filter_by(submitter_id=user.uid).first()
    if check is None:
        newsong = Song(request.form['song'], user.uid)
        db.session.add(newsong)
        db.session.commit()
    return redirect(url_for('page_dashboard'))


if __name__ == "__main__":
    # Se non esiste il database viene creato
    if not os.path.isfile("db.sqlite"):
        db.create_all()
        admin = User("admin", "password", True)
        db.session.add(admin)
        db.session.commit()
    app.run(host="0.0.0.0", debug=True)