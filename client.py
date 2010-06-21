#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple EDACC client fetching a random job from an experiment for testing purposes """

import time, sys, subprocess, os, resource, StringIO, shlex, threading, multiprocessing
from datetime import datetime
from edacc.models import session, Experiment, ExperimentResult
from edacc.utils import launch_command
from sqlalchemy.sql.expression import func

def setlimits(cputime, mem):
    resource.setrlimit(resource.RLIMIT_CPU, (cputime, cputime + 1))
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))

def fetch_resources(experiment_id):
    try:
        os.mkdir('/tmp/edacc')
        os.mkdir('/tmp/edacc/solvers')
        os.mkdir('/tmp/edacc/instances')
    except: pass
    
    experiment = session.query(Experiment).get(experiment_id)
    
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
            
class EDACCClient(threading.Thread):
    count = 0
    def __init__(self, experiment_id):
        super(EDACCClient, self).__init__(group=None)
        self.experiment = session.query(Experiment).get(experiment_id)
        self.name = str(EDACCClient.count)
        EDACCClient.count += 1
        
    def run(self):
        if self.experiment is None: return
        experiment = self.experiment
        while True:
            job = session.query(ExperimentResult) \
                        .filter_by(experiment=self.experiment) \
                        .filter_by(status=-1) \
                        .order_by(func.rand()).limit(1).first()
            if job:
                job.status = 0
                job.startTime = datetime.now()
                session.commit()
                
                client_line = '/tmp/edacc/solvers/' + launch_command(job.solver_configuration)[2:]
                client_line += '/tmp/edacc/instances/' + job.instance.name + ' ' + str(job.seed)
                print "running job", job.idJob, client_line
                stdout = open(self.name + 'stdout~', 'w')
                stderr = open(self.name + 'stderr~', 'w')
                p = subprocess.Popen(shlex.split(client_line), preexec_fn=setlimits(experiment.timeOut, experiment.memOut * 1024 * 1024), stdout = stdout, stderr = stderr)
                start = time.time()
                p.wait()
                runtime = time.time() - start
                job.time = runtime
                stdout.close()
                stderr.close()
                stdout = open(self.name + 'stdout~', 'r')
                stderr = open(self.name + 'stderr~', 'r')
                job.resultFile = "STDOUT:\n\n" + stdout.read() + "\n\nSTDERR:\n\n" + stderr.read()
                stdout.close()
                stderr.close()
                
                job.clientOutput = "this solver is damn slooooow, it's friday and I want to go home :-("
                print "... done (took " + str(runtime) + " s)"
                if runtime > experiment.timeOut:
                    job.status = 2
                else:
                    job.status = 1
                    
                session.commit()
            else: break
            
    

if __name__ == '__main__':
    exp_id = int(raw_input('Enter experiment id: '))
    experiment = session.query(Experiment).get(exp_id)
    if experiment is None:
        print "Experiment doesn't exist"
        sys.exit(0)
    
    fetch_resources(exp_id)
    
    print "Starting up .. using " + str(experiment.grid_queue[0].numCPUs) + " threads"
    clients = [EDACCClient(exp_id) for _ in xrange(experiment.grid_queue[0].numCPUs)]
    for c in clients:
        c.start()
    for c in clients:
        c.join()