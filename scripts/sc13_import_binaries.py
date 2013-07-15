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
    for filename in os.listdir('.'):
        if not (os.path.isdir(filename) and len(filename) == 32): continue # only consider dirs with md5 of code as name

        for dirname, dirnames, filenames in os.walk(filename):
            if not ('binary' in dirnames and 'build.sh' in filenames): continue

            binary_path = os.path.join(dirname, 'binary')
            if len(os.listdir(binary_path)) == 0:
                print "Empty binary folder", binary_path
                continue

            md5 = filename
            solvers = db.session.query(db.Solver).filter(func.md5(db.Solver.code)==md5).all()
            if not solvers:
                print "Could not find matching solvers for code md5", md5
                continue

            for solver in solvers:
                print "Adding binary of solver", solver.name, solver.version

                runCommand = ''
                runPath = ''
                if solver.competition_launch_command: # command stored in DB
                    command = solver.competition_launch_command
                else: # command still in text files
                    with open(filename + '.txt', 'r') as commandfile:
                        command = commandfile.read().strip()

                if len(command.split()) > 1: # most likely 'java -jar jarname' or similar
                    runCommand = ' '.join(command[:-1])
                    runPath = command[-1]
                else:
                    runCommand = ''
                    runPath = command

                print "Parsed run command (%s) and run path (%s)" % (runCommand, runPath)

                zf = tempfile.TemporaryFile(prefix='binary', suffix='.zip')
                zip = zipfile.ZipFile(zf, 'w', zipfile.ZIP_DEFLATED)
                for dirname, subdirs, files in os.walk(binary_path):
                    for fn in files:
                        absfn = os.path.join(dirname, fn)
                        zfn = absfn[len(binary_path)+len(os.sep):]
                        zip.write(absfn, zfn)
                zip.close()
                zf.seek(0)

                binary_md5 = hashlib.md5()
                binary_md5.update(zf.read())
                zf.seek(0)

                print "Adding new solver binary."
                solver_binary = db.SolverBinary()
                solver_binary.solver = solver
                solver_binary.binaryName = solver.name
                solver_binary.binaryArchive = zf.read()
                solver_binary.md5 = binary_md5.hexdigest()
                solver_binary.version = solver.version
                solver_binary.runCommand = runCommand
                solver_binary.runPath = runPath
                db.session.add(solver_binary)
                db.session.commit()

