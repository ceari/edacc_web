# -*- coding: utf-8 -*-

from flask import render_template as render
from flask import Response

from edacc import app, plots
from edacc.models import Solver, Session

@app.route('/')
def index():
    session = Session()
    solvers = session.query(Solver).all()

    return render('test.html', solvers=solvers)

@app.route('/imgtest')
def imgtest():
    return Response(response=plots.draw(), mimetype='image/png')