# resume-parser

The objective here is to make something to parse resumes for the 2018 HackNC
competition. These will be provided to certain sponsors.

Current ideas about the project:
  * Website written in Flask for sponsors to filter based on key metrics they
    want to see
  * Commandline tool that parses a resume and puts that information in a
    database

We will probably use some sort of natural language processing (NLP) to parse
structured data out of the resumes and into the database (e.g. classes,
education, previous occupations).

# Tooling

For this project we are using [poetry](https://poetry.eustace.io/). From their
[docs](https://poetry.eustace.io/docs/), they say the following: "Poetry is a
tool for dependency management and packaging in Python. It allows you to declare
the libraries your project depends on and it will manage (install/update) them
for you."

The docs have a tutorial on how to install it.

`poetry install` brings you up to date on dependencies and libraries used by
this project.

You can do `poetry add` to add a python library. 

`poetry shell` creates and runs a poetry virtual env, where all of the exact
libraries are installed.

Once you've opened a poetry shell, you can run `flask db init` to create the
database. `flask db migrate` will generate a migration based on what database
schema is currently in the code. 

`flask db upgrade` will run the migrations and update your database schema to the
current version.

# Website

I've created a basic Flask website, along with [Flask-SQLAlchemy](http://flask-sqlalchemy.pocoo.org/2.3/) and a migration tool ([Flask-Migrate](http://flask-sqlalchemy.pocoo.org/2.3/))

# CLI

Flask has a [cli](http://flask.pocoo.org/docs/1.0/cli/), which seems good for
creating a commandline tool that has access to the database created in Flask. 
