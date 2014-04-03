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

if __name__ == "__main__":
    for solver in db.session.query(db.Solver):
        if solver.user is None: continue

        remove_from = []
        for cat in solver.competition_categories:
            if cat.name.endswith("SAT"):
                for unsat_cat in solver.competition_categories:
                    if unsat_cat.name == cat.name + "+UNSAT":
                        print solver.name + " is both in " + cat.name + " and " + unsat_cat.name
                        remove_from.append(cat)

        for c in remove_from:
            print " removing from", c
            solver.competition_categories.remove(c)
        db.session.add(solver)

    try:
        db.session.commit()
    except Exception as e:
        print e
        db.session.rollback()