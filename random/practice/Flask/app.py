import os
import click
import datetime
from flask import Flask, redirect, request, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

# Creates the flask application
app = Flask(__name__)

# SQLALCHEMY_DATABASE_URI: Specifies the database location
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///event_database.db'

# Define db
db = SQLAlchemy(app)


try:
    os.makedirs(app.instance_path)
except OSError:
    pass


# Define the Event Model (Notice: date is db.String to match your route string formatting)
class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String, nullable=False)
    event = db.Column(db.String, nullable=False)


# Create the Database tables automatically on start if they don't exist
with app.app_context():
    db.create_all()


# CLI Command for 'flask init-db'
@app.cli.command("init-db")
def init_db_command():
    """Clear existing data and create new tables."""
    db.create_all()
    print("Initialized the database.")


# Routes
@app.route('/')
def hello_world():
    return "Hello World"


@app.route('/home', methods=["GET", "POST"])
def home():
    if request.method == "POST":
        db.session.add(
            Event(
                date=str(datetime.datetime.now()), # Simplified string conversion
                event=request.form["eventBox"],
            )
        )
        db.session.commit()
        return redirect(url_for('home'))
        
    return render_template(
        "home.html",
        eventsList=db.session.execute(
            db.select(Event).order_by(Event.date)
        ).scalars(),
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        name = request.form["username"]
        return f"Hello {name} POST request received"
    return render_template('name.html')


@app.route('/user/<username>')
def user(username):
    return f"HELLO, {username}!"



if __name__ == '__main__':
    app.run(debug=True)