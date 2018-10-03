from flask import Flask, render_template, request, send_from_directory, send_file, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug import secure_filename
from flask_login import LoginManager, login_user, login_required, logout_user
from flask_bcrypt import Bcrypt
import csv

import click
import os
import sys

import io
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage

import zipfile

from elasticsearch import Elasticsearch

es = Elasticsearch()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['UPLOAD_FOLDER'] = "resumes"
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

db = SQLAlchemy(app)
migrate = Migrate(app, db)

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

    es.index(index="hacknc-2018-index", doc_type='resume', id=hacker.id, body={'name': hacker.name, 'filename':hacker.filename, 'content': hacker.resume}) 

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

@app.route('/add', methods=['POST', 'GET'])
@login_required
def add_hacker():
    if request.method == 'POST':
        name = request.form['hacker-name']
        uploaded_file = request.files['file-upload']
        filename = secure_filename(uploaded_file.filename)
        path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], filename)
        uploaded_file.save(path)

        resume = convert_pdf_to_txt(path)
        hacker = Hacker(name, filename, resume)
        db.session.add(hacker)
        db.session.commit()
        es.index(index="hacknc-2018-index", doc_type='resume', id=hacker.id, body={'name': hacker.name, 'filename':hacker.filename, 'content': hacker.resume}) 
        return redirect(url_for("index"))
    else:
        return render_template('add.html')

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

@app.route('/downloadzip/<search>', methods=['GET'])
@app.route('/downloadzip/', methods=['GET'])
@app.route('/downloadzip', methods=['GET'])
@login_required
def download_zip(search=None):
    if search is None or len(search.split()) == 0:
        results = es.search(index="hacknc-2018-index", size=2000, body={"query": {"match_all": {}}})
    else:
        results = es.search(index="hacknc-2018-index", size=2000, body={"query":
            {"match": {'content': {'operator': 'and', 'query':
               search }}}})


    filenames = [f['_source']['filename'] for f in results['hits']['hits']]
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="a", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(app.config['UPLOAD_FOLDER'], compress_type=zipfile.ZIP_STORED)
        for filename in filenames:
            print(filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.utime(path,(1330712280, 1330712292))
            try:
                zip_file.write(path, compress_type=zipfile.ZIP_DEFLATED)
            except:
                print(filename + " something something file before 1980", file=sys.stderr)

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

            extension = filename.split(".")
            extension = extension[len(extension) - 1]

            name = row[0] + " " + row[1]

            if extension != "pdf":
                continue

            print(path)
            try:
                resume = convert_pdf_to_txt(path)
                hacker = Hacker(name, filename, resume)
                try:
                    db.session.add(hacker)
                    db.session.commit()
                    es.index(index="hacknc-2018-index", doc_type='resume', id=hacker.id, body={'name': hacker.name, 'filename':hacker.filename, 'content': hacker.resume}) 
                except:
                    print("already added or db error")

                print(hacker.name)
            except:
                print("error on " + filename + " with name " + name)

@app.cli.command()
@click.argument('name')
def search_hackers(name):
    es.indices.refresh(index="hacknc-2018-index")
    results = es.search(index="hacknc-2018-index", size=2000, body={"query": {"match": {'content': search}}})
    for result in results['hits']['hits']:
        print(result['_source']['name'])

@app.route("/", methods=['POST', 'GET'])
@login_required
def index():
    es.indices.refresh(index="hacknc-2018-index")

    if request.method == 'POST':
        if request.form['search'] is None or len(request.form['search'].split()) == 0:
            results = es.search(index="hacknc-2018-index", size=2000, body={"query": {"match_all": {}}})
            search = ""
        else:
            results = es.search(index="hacknc-2018-index", size=2000, body={"query":
                {"match": {'content': {'operator': 'and', 'query':
                    request.form['search']}}}})
            search = request.form['search']
    else:
        results = es.search(index="hacknc-2018-index", size=2000, body={"query": {"match_all": {}}})
        search = ""

    return render_template('search.html', results=results['hits']['hits'],
            total=results['hits']['total'], search=search)
