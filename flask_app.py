# https://flask.palletsprojects.com/en/1.1.x/
# flask

# https://werkzeug.palletsprojects.com/en/2.3.x/utils/
# security

from flask import Flask, redirect, render_template, request, session
from flask_session import Session
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# sqlite3 database setup
db_connection = sqlite3.connect("ecoride_db.sqlite", check_same_thread=False)
db = db_connection.cursor()

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # If user got to route by submitting register form POST method
    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        username = request.form.get("username")
        email = request.form.get("email")
        city = request.form.get("city")
        car = request.form.get("brand")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Error: missing an information input
        if not username:
            return render_template("register.html", error="Missing username")
        if not password:
            return render_template("register.html", error="Missing password")
        if not first_name:
            return render_template("register.html", error="Missing first name")
        if not last_name:
            return render_template("register.html", error="Missing last name")
        if not email:
            return render_template("register.html", error="Please provide an email")
        if not confirmation:
            return render_template("register.html", error="Please confirm password")
        if not city:
            return render_template("register.html", error="Missing city")
        if not car:
            return render_template("register.html", error="Missing car brand")

        # Error: username in use
        prior = db.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone()
        if prior != None:
            return render_template("register.html", error="Username already in use")

        # Error: password confirmation doesn't match
        if password != confirmation:
            return render_template("register.html", error="Passwords do not match")

        # Store username and password in table
        hashed_password = generate_password_hash(password)
        db.execute("INSERT INTO users (first_name, last_name, username, hash, car_model, city, email) VALUES (?, ?, ?, ?, ?, ?, ?)", (first_name, last_name, username, hashed_password, car, city, email))
        db_connection.commit()

        # Redirect user to login form
        return redirect("/login")

    # If user got to route by URL GET method
    else:
        return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    # clear session
    session.clear()

    # user submitted login form
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # check username exist
        if not username:
            return render_template("login.html", error="Missing username")
        # check password exist
        if not password:
            return render_template("login.html", error="Missing password")

        # get rows from users table that match username
        rows = db.execute("SELECT id, hash FROM users WHERE username = ?", (username,)).fetchall()

        # check at least 1 user exists with given username and password is correct
        if not (len(rows) >= 1):
            return render_template("login.html", error="No user exists with this username")
        if not check_password_hash(rows[0][1], password):
            return render_template("login.html", error="Wrong password")

        # start session for user
        session["user_id"] = rows[0][0]

        # redirect to home
        return redirect("/")

    # url link
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/host", methods=["GET", "POST"])
def host():
    if not session["user_id"]:
        return redirect("/login")
    
    # page to host rides (requires login)

    if request.method == "POST":
        date = request.form.get("drive_date")
        time = request.form.get("drive_time")

        # missing date or time
        if not (date):
            return render_template("host.html", error="Incomplete date")
        if not (time):
            return render_template("host.html", error="Incomplete time")

        driver = db.execute("SELECT id, drives, driver_rating, city FROM users WHERE id = ?", (session["user_id"],)).fetchone()

        year, month, day = date.split("-")
        date = month + "/" + day + "/" + day

        hour, minute = time.split(":")
        hour = int(hour)
        ending = ""
        if hour < 12:
            ending = "AM"
        else:
            ending = "PM"

        time = str(hour % 12) + ":" + str(minute) + " " + ending

        if driver[1] == 0:
            db.execute("INSERT INTO drives (user_id, city, date, time, rating) VALUES (?, ?, ?, ?, ?)", (session["user_id"], driver[3], date, time, driver[2]))
            db_connection.commit()
        else:
            db.execute("INSERT INTO drives (user_id, city, date, time, rating) VALUES (?, ?, ?, ?, ?)", (session["user_id"], driver[3], date, time, driver[2]))
            db_connection.commit()
        return redirect("/rides")
    else:
        return render_template("host.html")


@app.route("/rides", methods=["GET", "POST"])
def rides():
    if not session["user_id"]:
        return redirect("/login")

    # Page to look for rideshares (requires login)
    # POST if user submitted either drive choice or rating form
    if request.method == "POST":
        # if user submitted rating form
        if request.form.get("rate_id"):
            drive_id = request.form.get("rate_id")
            rating = request.form.get("rating")

            # missing information fields
            if not drive_id:
                return redirect("/rides", error_rating="Missing drive id")
            if not rating:
                return render_template("rides.html", error_rating="Missing rating")

            driver_id = db.execute("SELECT user_id FROM drives WHERE id = ?", (drive_id,)).fetchone()
            if not driver_id:
                return render_template("rides.html", error_rating="Invalid drive_id")

            driver_id = driver_id[0]

            db.execute("INSERT INTO ratings (user_id, driver_id, drive_id, rating) VALUES (?, ?, ?, ?)", (session["user_id"], driver_id, drive_id, rating))
            db_connection.commit()


            rating = db.execute("SELECT AVG(rating) FROM ratings WHERE driver_id = ?", (driver_id,)).fetchone()
            rating = rating[0]


            db.execute("UPDATE users SET driver_rating = ? WHERE id = ?", (rating, driver_id,))
            db_connection.commit()

            your_drives = db.execute("SELECT drives.id, first_name, last_name, drives.city, date, time, driver_rating, email FROM drives JOIN users ON drives.user_id=users.id WHERE drives.id IN (SELECT drive_id FROM books WHERE user_id = ?)", (session["user_id"],)).fetchall()
            available_drives = db.execute("SELECT drives.id, drives.city, date, time, driver_rating FROM drives JOIN users ON drives.user_id=users.id WHERE drives.city IN (SELECT city FROM users WHERE id = ?)", (session["user_id"],)).fetchall()
            return render_template("rides.html", yours=your_drives, available=available_drives)
        # if user submitted drive choice
        elif request.form.get("drive_id"):
            drive_id = request.form.get("drive_id")

            if not drive_id:
                your_drives = db.execute("SELECT drives.id, first_name, last_name, drives.city, date, time, driver_rating, email FROM drives JOIN users ON drives.user_id=users.id WHERE drives.id IN (SELECT drive_id FROM books WHERE user_id = ?)", (session["user_id"],)).fetchall()
                available_drives = db.execute("SELECT drives.id, drives.city, date, time, driver_rating FROM drives JOIN users ON drives.user_id=users.id WHERE drives.city IN (SELECT city FROM users WHERE id = ?)", (session["user_id"],)).fetchall()
                return render_template("rides.html", error="No drive chosen", yours=your_drives, available=available_drives)


            drive_exists = db.execute("SELECT * FROM drives WHERE id = ?", (drive_id,))
            if not drive_exists:
                your_drives = db.execute("SELECT drives.id, first_name, last_name, drives.city, date, time, driver_rating, email FROM drives JOIN users ON drives.user_id=users.id WHERE drives.id IN (SELECT drive_id FROM books WHERE user_id = ?)", (session["user_id"],)).fetchall()
                available_drives = db.execute("SELECT drives.id, drives.city, date, time, driver_rating FROM drives JOIN users ON drives.user_id=users.id WHERE drives.city IN (SELECT city FROM users WHERE id = ?)", (session["user_id"],)).fetchall()
                return render_template("rides.html", error="This drive doesn't exist", yours=your_drives, available=available_drives)

            drive_available_in_city = db.execute("SELECT * FROM drives WHERE id = ? AND city IN (SELECT city FROM users WHERE id = ?)", (drive_id, session["user_id"]))
            if not drive_available_in_city:
                your_drives = db.execute("SELECT drives.id, first_name, last_name, drives.city, date, time, driver_rating, email FROM drives JOIN users ON drives.user_id=users.id WHERE drives.id IN (SELECT drive_id FROM books WHERE user_id = ?)", (session["user_id"],)).fetchall()
                available_drives = db.execute("SELECT drives.id, drives.city, date, time, driver_rating FROM drives JOIN users ON drives.user_id=users.id WHERE drives.city IN (SELECT city FROM users WHERE id = ?)", (session["user_id"],)).fetchall()
                return render_template("rides.html", error="This drive is not in your city", yours=your_drives, available=available_drives)

            db.execute("INSERT INTO books (user_id, drive_id) VALUES (?, ?)", (session["user_id"], drive_id))
            db_connection.commit()

        return redirect("/rides")
    # URL GET
    else:
        your_drives = db.execute("SELECT drives.id, first_name, last_name, drives.city, date, time, driver_rating, email FROM drives JOIN users ON drives.user_id=users.id WHERE drives.id IN (SELECT drive_id FROM books WHERE user_id = ?)", (session["user_id"],)).fetchall()
        available_drives = db.execute("SELECT drives.id, drives.city, date, time, driver_rating FROM drives JOIN users ON drives.user_id=users.id WHERE drives.city IN (SELECT city FROM users WHERE id = ?)", (session["user_id"],)).fetchall()

        return render_template("rides.html", drives=available_drives, yours=your_drives)