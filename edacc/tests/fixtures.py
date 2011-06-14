# -*- coding: utf-8 -*-
"""
    EDACC Web Frontend Test Fixtures
    --------------------------------

    Fixtures (test data) used in the unit tests.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import datetime

def setup_ranking_fixture(db):
    """Creates and commits test data to the passed in database
    used in the ranking unit tests.
    """
    sc = db.StatusCodes()
    sc.statusCode = 1
    sc.description = u"finished"
    db.session.add(sc)

    rc = db.ResultCodes()
    rc.resultCode = 11
    rc.description = u'SAT'
    db.session.add(rc)

    for i in range(10):
        s = db.Solver()
        sb = db.SolverBinary()
        sb.solver = s
        sb.binaryName = u"TestSolverBinary"
        sb.binaryArchive = u"dummy"
        sb.md5 = u"dummy"
        sb.version = u"dummy"
        sb.runCommand = u"dummy"
        sb.runPath = u"dummy"
        s.name = u"TestSolver" + str(i)
        s.description = u"TestSolver" + str(i)
        s.code = u" dummy"
        s.version = u"dummy"
        s.authors = u"dummy"
        db.session.add(s)
        db.session.add(sb)

    ic = db.InstanceClass()
    ic.name = u"TestInstanceClass"
    ic.description = u"dummy"
    ic.source = True
    db.session.add(ic)

    for i in range(10):
        inst = db.Instance()
        inst.name = u"TestInstance" + str(i)
        inst.instance = u"dummy"
        inst.md5 = u"dummy" + str(i)
        inst.source_class = ic
        db.session.add(inst)

    db.session.commit()

    exp = db.Experiment()
    exp.name = u"TestExperiment"
    exp.description = u"dummy"
    exp.date = datetime.date(2011, 1, 1)
    exp.linkSeeds = True
    exp.autoGeneratedSeeds = True
    exp.active = True
    exp.instances = db.session.query(db.Instance).all()
    db.session.add(exp)

    db.session.commit()

    for s in db.session.query(db.Solver).all():
        sc = db.SolverConfiguration()
        sc.seed_group = 0
        sc.solver = s
        sc.name = s.name + u"Configuration"
        sc.solver_binary = s.binaries[0]
        sc.idx = 0
        sc.experiment = exp
        db.session.add(sc)

    db.session.commit()

    sc_i = 0
    for sc in sorted(exp.solver_configurations, key=lambda sc: str(sc)):
        sc_i += 1
        for instance in exp.instances:
            for run in range(10):
                er = db.ExperimentResult()
                er.instance = instance
                er.solver_configuration = sc
                er.experiment = exp
                er.run = run
                er.status = 1
                er.CPUTimeLimit = 100
                er.wallClockTimeLimit = er.memoryLimit = er.stackSizeLimit = er.outputSizeLimitFirst = er.outputSizeLimitLast = -1
                er.resultCode = 11
                er.date_modified = datetime.date(2011, 1, 1)
                er.priority = 0
                er.resultTime = sc_i
                db.session.add(er)

    db.session.commit()
