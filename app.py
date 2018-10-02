from flask import Flask, render_template, request, send_from_directory, send_file, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_msearch import Search
from werkzeug import secure_filename
from flask_login import LoginManager, login_user, login_required, logout_user
from flask_bcrypt import Bcrypt
import csv

import click
import os

import io
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage

import zipfile
import zlib

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['UPLOAD_FOLDER'] = "resumes"
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['ZIP_FOLDER'] = "tmp"

db = SQLAlchemy(app)
migrate = Migrate(app, db)

search = Search()
search.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = "login"

bcrypt = Bcrypt(app)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    password_hash = db.Column(db.String(500))

    def __init__(self, name, password):
        self.name = name
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

class Hacker(db.Model):
    __tablename__ = 'hacker'
    __searchable__ = ['name', 'resume']

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    filename = db.Column(db.Text)
    resume = db.Column(db.Text)

    def __init__(self, name, filename, resume):
        self.name = name
        self.filename = filename
        self.resume = resume

def convert_pdf_to_txt(path):
    rsrcmgr = PDFResourceManager()
    retstr = io.StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    fp = open(path, 'rb')
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos = set()

    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages,
                                  password=password,
                                  caching=caching,
                                  check_extractable=True):
        interpreter.process_page(page)

    text = retstr.getvalue()

    fp.close()
    device.close()
    retstr.close()
    return text

@app.cli.command()
@click.argument('name')
@click.argument('path')
def create_hacker(name, path):
    resume = convert_pdf_to_txt(path)
    hacker = Hacker(name, path, resume)
    db.session.add(hacker)
    db.session.commit()

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        name = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(name=name).first()
        if user is not None:
            if user.check_password(password):
                login_user(user)

        return redirect(url_for("index"))
    else:
        return render_template("login.html")

@app.route('/add', methods=['POST'])
@login_required
def add_hacker():
    name = request.form['hacker-name']
    uploaded_file = request.files['file-upload']
    filename = secure_filename(uploaded_file.filename)
    path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], filename)
    uploaded_file.save(path)

    resume = convert_pdf_to_txt(path)
    hacker = Hacker(name, filename, resume)
    db.session.add(hacker)
    db.session.commit()
    return redirect(url_for("index"))

@app.route('/search', methods=['POST', 'GET'])
@login_required
def search():
    results = Hacker.query.msearch(request.form['search'], or_=True)
    return render_template('search.html', results=results, search=request.form['search'])

@app.route('/all')
@login_required
def all():
    results = Hacker.query.all()
    return render_template('search.html', results=results)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

@app.route('/downloadzip/<search>', methods=['GET'])
@login_required
def download_zip(search):
    results = Hacker.query.msearch(search, or_=True)
    filenames = [f.filename for f in results]
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for filename in filenames:
                zip_file.write(app.config['UPLOAD_FOLDER'] + '/' + filename)
    zip_buffer.seek(0)
    return send_file(zip_buffer, attachment_filename='HackNC_Resumes_Search_{}.zip'.format(search), as_attachment=True)

@app.cli.command()
@click.argument('name')
@click.argument('password')
def add_user(name, password):
    user = User(name, password)
    db.session.add(user)
    db.session.commit()

@app.cli.command()
@click.argument('filename')
def bulk_upload(filename):
    with open(filename, 'r') as f:
        csv_reader = csv.reader(f, delimiter=',')
        for i, row in enumerate(csv_reader):
            if i == 0:
                continue
            custom = row[2].split("-")
            if custom[0].strip() == "custom":
                print(custom)
                filename = row[0] + row[1] + ".pdf"
                path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], filename)
            else:
                split = row[2].split("/")
                filename = split[len(split) - 2]
                path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], filename)

            resume = convert_pdf_to_txt(path)
            hacker = Hacker(name, filename, resume)
            db.session.add(hacker)
            db.session.commit()


@app.cli.command()
@click.argument('name')
def search_hackers(name):
    results = Hacker.query.msearch(name)
    for result in results:
        print(result.name)

@app.cli.command()
def create_index():
    search.create_index(update=True)

@app.route("/")
@login_required
def index():
    return render_template("index.html")
