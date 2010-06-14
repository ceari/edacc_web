#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Simple EDACC client fetching random jobs from an experiment and writing pseudo results
    for testing purposes """

import time, random, sys
from edacc.models import session, Experiment, ExperimentResult
from sqlalchemy.sql.expression import func

if __name__ == '__main__':
    random.seed()
    experiment_id = int(raw_input("Enter experiment id: "))
    experiment = session.query(Experiment).get(experiment_id)
    if experiment is None:
        print "experiment doesn't exist"
        sys.exit(0)
    
    while True:
        job = session.query(ExperimentResult) \
                    .filter_by(experiment=experiment) \
                    .filter_by(status=-1) \
                    .order_by(func.rand()).limit(1).first()
        if job:
            print "running job " + str(job.idJob)
            job.status = 0
            session.commit()
            time.sleep(1)
            job.status = 3
            job.time = random.randint(100, 1000)
            session.commit()
        else: break
    
    for job in session.query(ExperimentResult).filter_by(experiment=experiment).all():
        job.status = -1
    
    session.commit()