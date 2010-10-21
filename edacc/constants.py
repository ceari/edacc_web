# -*- coding: utf-8 -*-
"""
    edacc.constants
    ---------------

    Application logic constants used in the database and the Java Swing
    application.
"""

# enum of possible property value types (propertyValue column in the Property table)
INSTANCE_PROPERTY_TYPE = 0
RESULT_PROPERTY_TYPE = 1

STATUS_LAUNCHER_CRASH = -5
STATUS_WATCHER_CRASH = -4
STATUS_SOLVER_CRASH = -3
STATUS_VERIFIER_CRASH = -2
STATUS_NOT_STARTED = -1
STATUS_RUNNING = 0
STATUS_FINISHED = 1

STATUS_ERRORS = (STATUS_LAUNCHER_CRASH,
                 STATUS_WATCHER_CRASH,
                 STATUS_SOLVER_CRASH,
                 STATUS_VERIFIER_CRASH)

STATUS_PROCESSING = (
    STATUS_NOT_STARTED,
    STATUS_RUNNING)

STATUS_EXCEEDED_LIMITS = (
    21,22,23,24,25
)

# status id to string map
JOB_STATUS = {
    -5: 'launcher crash',
    -4: 'watcher crash',
    -3: 'solver crash',
    -2: 'verifier crash',
    -1: 'not started',
    0:  'running',
    1:  'finished',
    21: 'terminated by ulimit',
    22: 'terminated by ulimit',
    23: 'terminated by ulimit',
    24: 'terminated by ulimit',
    25: 'terminated by ulimit',
}

JOB_RESULT_CODE = {
    11: 'SAT',
    10: 'UNSAT',
    0: 'UNKNOWN',
    -1: 'wrong answer',
    -21: 'cpu time limit exceeded',
    -22: 'wall clock time limit exceeded',
    -23: 'memory limit exceeded',
    -24: 'stack size limit exceeded',
    -25: 'output size limit exceeded',
}

JOB_RESULT_CODE_COLOR = {
    11: '#00CC33',
    10: '#00CC33',
    0: '#D3D3D3',
    -21: 'red',
    -22: 'red',
    -23: 'red',
    -24: 'red',
    -25: 'red',
}

JOB_STATUS_COLOR = {
    -5: '#FF0000',
    -4: '#FF0000',
    -3: '#FF0000',
    -2: '#FF0000',
    -1: '#4169E1',
    0:  'orange',
    1:  '#00CC33',
    2:  '#FF6600',
    21: '#FF6600',
}

OWN_RESULTS = set([3, 4, 5])        # phases where own results are shown
ALL_RESULTS = set([6, 7])           # phases where all results are shown
INSTANCE_DETAILS = set([6, 7])      # phases where full access to instance details/downloads is granted
ANALYSIS1 = set([5, 6, 7])          # phases where some plots are shown (cactus)
ANALYSIS2 = set([6, 7])             # phases where the other plots are shown
RANKING = set([6, 7])               # phases where ranking is shown
