from app import app
from flask import render_template
from app.forms import LoginForm

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', title='Home')

@app.route('/login')
def login():
    form = LoginForm()
    return render_template('login_page.html', title='Login', form=form)

@app.route('/map')
def map():
    return render_template('map.html', title='Map')