
from flask import render_template as render

from edacc import app
from edacc.models import Solver, Session

@app.route('/')
def index():
    session = Session()
    solvers = session.query(Solver).all()
    
    return render('test.html', solvers=solvers)

