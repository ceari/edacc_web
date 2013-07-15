import sys, os, zipfile, tempfile, hashlib

sys.path.append("/srv/edacc_web")
sys.path.append("/srv/edacc_web/scripts")
sys.path.append("..")
try:
    activate_this = '/srv/edacc_web/env/bin/activate_this.py'
    execfile(activate_this, dict(__file__=activate_this))
except:
    pass

from sqlalchemy.sql import func

from edacc import models, config, constants
from satcomp13_config import *

db = models.add_database(DB_USER, DB_PASSWORD, DB_NAME, DB_NAME)

def cat_by_exp_id(exp_id):
    for cat_name, exp in test_experiments.items():
        if exp[0] == exp_id:
            return db.session.query(db.CompetitionCategory).filter_by(name=cat_name).first()
    return None

if __name__ == "__main__":
    for line in data.split('\n'):
        l = map(str.strip, line.split("|"))
        solver_id = int(l[2])
        exp_id = int(l[3])

        solver = db.session.query(db.Solver).get(solver_id)
        comp_cat = cat_by_exp_id(exp_id)

        if comp_cat in solver.competition_categories:
            print "Removing " + solver.name + " from " + comp_cat.name
            solver.competition_categories.remove(comp_cat)

        db.session.add(solver)

    try:
        #db.session.commit()
        pass
    except Exception as e:
        print e
        db.session.rollback()
