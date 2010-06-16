# -*- coding: utf-8 -*-
"""
    Application logic constants used in the database and the Java Swing application
"""

# tuples since there are 3 codes that mean 'finished'
JOB_ERROR = (-2,)
JOB_WAITING = (-1,)
JOB_RUNNING = (0,)
JOB_FINISHED = (1,2,3,)

# status id to string map
JOB_STATUS = {-2: 'error',
              -1: 'not started',
              0: 'running',
              1: 'finished',
              2: 'terminated by ulimit',
              3: 'terminated by ulimit'}

JOB_STATUS_COLOR = {-2: '#FF0000',
                    -1: '#4169E1',
                    0: 'orange',
                    1: '#00CC33',
                    2: '#00CC33',
                    3: '#00CC33'}
