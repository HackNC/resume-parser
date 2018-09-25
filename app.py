from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_msearch import Search
from werkzeug import secure_filename
from flask import send_from_directory

import click
import os

import io
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['UPLOAD_FOLDER'] = "resumes"

db = SQLAlchemy(app)
migrate = Migrate(app, db)

search = Search()
search.init_app(app)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))

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

@app.route('/add', methods=['POST'])
def add_hacker():
    name = request.form['hacker-name']
    uploaded_file = request.files['file-upload']
    filename = secure_filename(uploaded_file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    uploaded_file.save(path)

    resume = convert_pdf_to_txt(path)
    hacker = Hacker(name, filename, resume)
    db.session.add(hacker)
    db.session.commit()
    return "done"

@app.route('/search', methods=['POST', 'GET'])
def search():
    results = Hacker.query.msearch(request.form['search'])
    return render_template('search.html', results=results)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

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
def index():
    return render_template("index.html")
