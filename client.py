#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple EDACC client fetching a random job from an experiment for testing purposes """

import time, random, sys, subprocess, os, resource, StringIO, shlex
from edacc.models import session, Experiment, ExperimentResult
from edacc.utils import launch_command
from sqlalchemy.sql.expression import func

def setlimits(cputime, mem):
    resource.setrlimit(resource.RLIMIT_CPU, (cputime, cputime + 1))
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))

if __name__ == '__main__':
    random.seed()
    experiment_id = int(raw_input("Enter experiment id: "))
    experiment = session.query(Experiment).get(experiment_id)
    if experiment is None:
        print "experiment doesn't exist"
        sys.exit(0)
    
    try:
        os.mkdir('/tmp/edacc')
        os.mkdir('/tmp/edacc/solvers')
        os.mkdir('/tmp/edacc/instances')
    except: pass
        
    for i in experiment.instances:
        if not os.path.exists('/tmp/edacc/instances/' + i.name):
            f = open('/tmp/edacc/instances/' + i.name, 'w')
            f.write(i.instance)
            f.close()
    
    for s in set(sc.solver for sc in experiment.solver_configurations):
        if not os.path.exists('/tmp/edacc/solvers/' + s.binaryName):
            f = open('/tmp/edacc/solvers/' + s.binaryName, 'w')
            f.write(s.binary)
            f.close()
            os.chmod('/tmp/edacc/solvers/' + s.binaryName, 0744)
        
    
    while True:
        job = session.query(ExperimentResult) \
                    .filter_by(experiment=experiment) \
                    .filter_by(status=-1) \
                    .order_by(func.rand()).limit(1).first()
        if job:
            job.status = 0
            session.commit()
            
            client_line = '/tmp/edacc/solvers/' + launch_command(job.solver_configuration)[2:]
            client_line += '/tmp/edacc/instances/' + job.instance.name + ' ' + str(job.seed)
            print "running job", job.idJob, client_line
            stdout = open(str(os.getpid()) + 'stdout~', 'w')
            stderr = open(str(os.getpid()) + 'stderr~', 'w')
            p = subprocess.Popen(shlex.split(client_line), preexec_fn=setlimits(experiment.timeOut, experiment.memOut * 1024 * 1024), stdout = stdout, stderr = stderr)
            start = time.time()
            p.wait()
            runtime = time.time() - start
            job.time = runtime
            stdout.close()
            stderr.close()
            stdout = open(str(os.getpid()) + 'stdout~', 'r')
            stderr = open(str(os.getpid()) + 'stderr~', 'r')
            job.resultFile = "STDOUT:\n\n" + stdout.read() + "\n\nSTDERR:\n\n" + stderr.read()
            stdout.close()
            stderr.close()
            
            job.clientOutput = "this solver is damn slooooow, it's friday and I want to go home :-("
            #print "result:", job.resultFile
            #print "exit code:", p.returncode
            print "... done (took " + str(runtime) + " s)"
            if runtime > experiment.timeOut:
                job.status = 2
            else:
                job.status = 1
                
            session.commit()
        else: break
    
    #session.commit()
