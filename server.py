from flask import Flask, session, url_for, redirect, request, render_template, abort
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import os
import threading
import vlc
import youtube_dl
import threading

app = Flask(__name__)
app.secret_key = "solello"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
service_started = False
skip = False
finished_downloading = True


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


def download_song(search, name):
    print("I'm inside the downloader")
    outtmpl = name + '.%(ext)s'
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': outtmpl,
        'postprocessors': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3',
             'preferredquality': '192',
             },
            {'key': 'FFmpegMetadata'},
        ],
    }
    print("I'm about to download stuff.")
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url="ytsearch:{}".format(search), download=True)


def streamer():
    global skip
    global service_started
    service_started = True
    already_added = False
    last_was_filler = True
    first_run = True
    songs = []
    global finished_downloading
    print("I'm here.")
    try:
    	inst = vlc.Instance()
    except Exception as e:
    	print(e)
    lista = inst.media_list_new()
    opzioni = "sout=#transcode{acodec=mp3,ab=192,channels=2,samplerate=44100}:http{dst=:8090/file.mp3}"
    lista.add_media(inst.media_new("static/elevatormusic.mp3", opzioni))
    print("Stream started over port 8090.")
    p = inst.media_list_player_new()
    p.set_media_list(lista)
    p.play()
    songs.append("Filler")
    try:
        while True:
            try:
                song = Song.query.filter_by(playing=False).first()
            except Exception as e:
                print(e)
                song = None
            if not song and not already_added:
                print("Branch 1")
                lista.add_media(inst.media_new("static/elevatormusic.mp3", opzioni))
                print("     Now playing elevator music. Enjoy.")
                p.set_media_list(lista)
                print("     List set")
                already_added = True
                last_was_filler = True
                songs.append("Filler")
                print(songs)
            elif song and not already_added:
                try:
                    finished_downloading = False
                    print("Branch 2")
                    download_song(song.name, song.name)
                    print("     Downloaded song")
                    lista.add_media(inst.media_new(song.name + ".mp3", opzioni))
                    print("Now playing the user's music. Have fun.")
                    p.set_media_list(lista)
                    song.playing = True
                    db.session.commit()
                    already_added = True
                    if last_was_filler:
                        p.next()
                        songs.pop(0)
                    if first_run:
                        p.next()
                        first_run = False
                        songs.pop(0)
                    last_was_filler = False
                    finished_downloading=True
                    songs.append(song.name)
                    print(songs)
                except:
                    db.session.delete(song)
                    db.session.commit()
                    print("Something happened while downloading.")
                    finished_downloading = True
                    already_added = False
            if finished_downloading:
                song_time = p.get_state()
                if str(song_time) == "State.Ended" or skip:
                    print("Ho skippato!")
                    already_added = False
                    try:
                        song_delete = Song.query.filter_by(playing=True).first()
                        db.session.delete(song_delete)
                        db.session.commit()
                    except:
                        pass
                    p.next()
                    skip = False
                    songs.pop(0)
                    print(songs)
    except Exception as e:
        print(e)
        p.stop()


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
    global service_started
    print(service_started)
    if 'username' not in session or 'username' is None:
        return redirect(url_for('page_login'))
    user = find_user(session['username'])
    currentSong = Song.query.filter_by(playing=True).first()
    songs = Song.query.filter_by(playing=False).limit(10).all()
    return render_template("/dashboard.htm", user=user, currentSong=currentSong, songs=songs)


@app.route("/user_add", methods=["GET", "POST"])
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
        return redirect(url_for('page_user_list'))


@app.route("/user_mod/<int:uid>", methods=["GET", "POST"])
def page_user_mod(uid):
    if 'username' not in session or 'username' is None:
        return redirect(url_for('page_login'))
    user = find_user(session['username'])
    if user.uid != uid and not user.isAdmin:
        return abort(403)
    utente = User.query.get_or_404(uid)
    if request.method == "GET":
        return render_template("user/mod.htm", utente=utente, user=user)
    else:
        if request.form["password"] != "":
            p = bytes(request.form["password"], encoding="utf-8")
            utente.password = bcrypt.hashpw(p, bcrypt.gensalt())
            db.session.commit()
            return redirect(url_for('page_dashboard'))


@app.route("/user_list")
def page_user_list():
    if 'username' not in session or 'username' is None:
        return redirect(url_for('page_login'))
    user = find_user(session['username'])
    if not user.isAdmin:
        return abort(403)
    utenti = User.query.all()
    if request.method == "GET":
        return render_template("user/list.htm", utenti=utenti, user=user)


@app.route("/addSong", methods=["POST"])
def api_song_add():
    if 'username' not in session or 'username' is None:
        return abort(403)
    user = find_user(session['username'])
    check = Song.query.filter_by(submitter_id=user.uid).first()
    if check is None or user.isAdmin:
        newsong = Song(request.form['song'], user.uid)
        db.session.add(newsong)
        db.session.commit()
    return redirect(url_for('page_dashboard'))


@app.route("/next")
def api_song_next():
    global skip
    if 'username' not in session or 'username' is None:
        return redirect(url_for('page_login'))
    user = find_user(session['username'])
    if not user.isAdmin:
        return abort(403)
    skip = True
    return redirect(url_for('page_dashboard'))


@app.route("/worker")
def api_worker():
    if not service_started:
        print("Service not started. Now starting the Thread...")
        try:
            t = threading.Thread(target=streamer())
            t.run()
        except:
            print("Something happened while starting the worker.")
    abort(500)


if __name__ == "__main__":
    # Se non esiste il database viene creato
    if not os.path.isfile("db.sqlite"):
        db.create_all()
        admin = User("admin", "password", True)
        db.session.add(admin)
        db.session.commit()
    app.run(host="0.0.0.0", debug=True, threaded=True)
