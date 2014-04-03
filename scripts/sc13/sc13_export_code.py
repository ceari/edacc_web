import sys, os, zipfile, tempfile, hashlib, shutil

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
    code_log_path = "/media/SATBENCH/satcompetition13/uploads/solvers/"

    # copy over txt file with launch command
    for dirname, dirnames, filenames in os.walk(code_log_path):
        for f in filenames:
            if len(f) == 32 + len('.txt') and f.endswith('.txt'):
                shutil.copy(os.path.join(dirname, f), '.')

    for solver in db.session.query(db.Solver):
        if solver.user is None: continue # only consider submitted solvers
        if len(solver.binaries) > 0: continue # only consider solvers without solver binary (new code)

        code_md5 = hashlib.md5()
        code_md5.update(solver.code)

        if not os.path.exists(code_md5.hexdigest() + '.txt') and not solver.competition_launch_command:
            print "Missing file/DB entry with run command of solver", solver.name, solver.version, code_md5.hexdigest()
            continue

        print "Writing", code_md5.hexdigest() + '.zip', "of solver", solver.name, solver.version, code_md5.hexdigest()

        with open(code_md5.hexdigest() + '.zip', 'wb') as codefile:
            codefile.write(solver.code)

        with open(code_md5.hexdigest() + '.author', 'w') as emailfile:
            emailfile.write(solver.user.email)