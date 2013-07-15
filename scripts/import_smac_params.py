import time, sys, random, os, subprocess
from datetime import datetime

random.seed(1)
sys.path.append("/home/share/edacc_web")
activate_this = '/srv/edacc_web/env2/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

from edacc import models, config, constants

if __name__ == "__main__":
    if len(sys.argv) < 6:
        print "Usage: python2 import_smac_params.py <username> <password> <database> <solver_name> <smac_params_file>"
        sys.exit()

    db_user = sys.argv[1]
    db_passwd = sys.argv[2]
    db_name = sys.argv[3]
    solver_name = sys.argv[4]
    smac_file = sys.argv[5]

    db = models.add_database(db_user, db_passwd, db_name, db_name)
    solver = db.session.query(db.Solver).filter_by(name=solver_name).first()

    if not solver:
        print "Solver not found."

    with open(smac_file) as f:
        for line in f:
            if not line: continue
            if len(line.split()) < 2: continue
            param_name = line.split()[0]
            param_values = line.split()[1]
            if not param_name: continue

            param = db.Parameter()
            param.name = param_name
            if "{}" in param_values:
                param.prefix = "-" + param_name
                param.hasValue = False
            else:
                param.prefix = "-" + param_name + "="
                param.hasValue = True
            param.defaultValue = ""
            param.order = len(solver.parameters)
            param.mandatory = False
            param.space = False
            param.attachToPrevious = False
            solver.parameters.append(param)

            print param.name, param.prefix, param.hasValue, param.order

    try:
        db.session.commit()
    except Exception as e:
        print e
        db.session.rollback()



