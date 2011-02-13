# -*- coding: utf-8 -*-
"""
    SAT Competition 2009 results import script
"""
import os, sys, datetime
sys.path.append("..") # append parent directory to python path to be able to import edacc when running from ./scripts
from edacc import models, config

config.DATABASE_HOST = "localhost"
models.add_database("edacc", "edaccteam", "EDACC5", "EDACC5")
db = models.get_database("EDACC5")

# mapping the "checked answer" column to EDACC's status/resultCode codes
ANSWER_MAP = {
    'UNKNOWN':          (1, 0),
    'UNKNOWN EXCODE':   (1, 0),
    'UNKNOWN TO':       (21, -21),
    'UNKNOWN MO':       (23, -23),
    'UNKNOWN (?)':      (1, 0),
    'SIGNAL':           (21, -309),
    'SAT':              (1, 11),
    'UNSAT':            (1, 10),
    'ERR WRONGCERT':    (1, -1),
    'ERR NOCERT':       (1, -1),
    'ERR UNSAT':        (1, -1),
}

def parse_phase_txt(filepath, phase):
    experiments = {'RANDOM': db.Experiment(), 'CRAFTED': db.Experiment(), 'APPLICATION': db.Experiment()}
    for exp in experiments.keys():
        experiments[exp].name = 'phase' + str(phase) + ' ' + exp
        experiments[exp].description = 'imported'
        experiments[exp].date = datetime.datetime.now()
        experiments[exp].maxSeed = 10000000
        experiments[exp].linkSeeds = False
        experiments[exp].autoGeneratedSeeds = True
        experiments[exp].memoryLimit = -1
        experiments[exp].stackSizeLimit = -1
        experiments[exp].outputSizeLimit = -1
        db.session.add(experiments[exp])
    
    # hardcoded limits as inferred from the data
    if phase == 2:
        experiments['APPLICATION'].CPUTimeLimit = 10000
        experiments['APPLICATION'].wallClockTimeLimit = 10000
        experiments['RANDOM'].CPUTimeLimit = 5000
        experiments['RANDOM'].wallClockTimeLimit = 5000
        experiments['CRAFTED'].CPUTimeLimit = 5000
        experiments['CRAFTED'].wallClockTimeLimit = 5000
    elif phase == 1:
        experiments['APPLICATION'].CPUTimeLimit = 1200
        experiments['APPLICATION'].wallClockTimeLimit = 1200
        experiments['RANDOM'].CPUTimeLimit = 1200
        experiments['RANDOM'].wallClockTimeLimit = 1200
        experiments['CRAFTED'].CPUTimeLimit = 1200
        experiments['CRAFTED'].wallClockTimeLimit = 1200
        
    db.session.commit()
    
    with open(filepath) as fh:
        num_lines = sum(1 for line in fh)
    
    print "Parsing results"
    i = 0
    solvers = {}
    solver_configs = {}
    instances = {}
    with open(filepath) as fh:
        fh.readline()
        fh.readline()
        for line in fh:
            i += 1
            if i % 10000 == 0: print i, '/', num_lines-2
            data = map(str.strip, line.split('|'))
            category, instance_path, answer, cputime, walltime, \
                solver_name, solver_version =   data[0], data[1], data[2], float(data[3]), float(data[4]), \
                                                data[5], data[6]
            
            instance_name = instance_path.split('/')[-1]
            if instance_name not in instances:
                # new instance, add to cache
                instances[instance_name] = db.session.query(db.Instance).filter_by(name=instance_name).first()
                experiments[category].instances.append(instances[instance_name])
                if instances[instance_name] is None:
                    # instance is not in the database yet, which is bad ...
                    print "Instance " + instance_name + " hasn't been found in the database! aborting ..."
                    sys.exit(1)
                
            solver_ident = (solver_name, solver_version)
            if not solver_ident in solvers: # new solver
                ex_solver = db.session.query(db.Solver).filter_by(name=solver_name, version=solver_version).first()
                if ex_solver:
                    solver = ex_solver
                else:
                    solver = db.Solver()
                    solver.name = solver_name
                    solver.version = solver_version
                    solver.binaryName = solver_name
                    solver.binary = "dummy"
                    solver.md5 = solver_name + solver_version
                    solver.authors = "-"
                    solver.description = "-"
                    db.session.add(solver)
                solvers[solver_ident] = solver
            else:
                solver = solvers[solver_ident]
                
            solver_config_ident = (category, solver_name, solver_version)
            if not solver_config_ident in solver_configs:
                # create solver config and add it to the experiment
                solver_config = db.SolverConfiguration()
                solver_config.solver = solver
                solver_config.name = solver_name + " " + solver_version
                solver_config.idx = 0
                solver_config.seed_group = 0
                solver_config.experiment = experiments[category]
                db.session.add(solver_config)
                solver_configs[solver_config_ident] = solver_config
                
            experiment = experiments[category]
            solver_config = solver_configs[(category, solver_name, solver_version)]
            instance = instances[instance_path.split('/')[-1]]
            
            er = db.ExperimentResult()
            er.instance = instance
            er.experiment = experiment
            er.solver_configuration = solver_config
            er.status = ANSWER_MAP[answer][0]
            er.resultCode = ANSWER_MAP[answer][1]
            er.seed = 0
            er.run = 0
            er.resultTime = cputime
            er.date_modified = datetime.datetime.now()
            er.priority = 0
            db.session.add(er)
        
    print "Writing to DB"
    db.session.commit()
    db.session.flush()
            
if __name__ == '__main__':
    import time
    dir = raw_input("Warning: Existing experiments and solvers will be deleted!! Enter phase files directory: ")
    start_time = time.clock()
    db.session.query(db.ExperimentResult).delete()
    db.session.query(db.Experiment).delete()
    db.session.query(db.Solver).delete()
    db.session.commit()
    print "Importing phase1.txt"
    parse_phase_txt(os.path.join(dir, "phase1.txt"), 1)
    print "Importing phase2.txt\n==========================================="
    parse_phase_txt(os.path.join(dir, "phase2.txt"), 2)
    print "Done. Imported data in ", time.clock() - start_time, "s"
    