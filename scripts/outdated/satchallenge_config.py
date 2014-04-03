DB_NAME = "EDACC"
DB_USER = "edacc"
DB_PASSWORD = "edaccteam"

base_url = 'http://edacc3.informatik.uni-ulm.de/SATChallenge2012/'

# competition category - test experiment (id, cpu time limit, wall time limit, memory limit)  mapping
test_experiments = {
    "Random SAT": (8, 30 -1, -1),
}

try:
    from satchallenge_local_config import *
except:
    pass



