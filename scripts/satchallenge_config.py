DB_NAME = "EDACC"
DB_USER = "edacc"
DB_PASSWORD = "edaccteam"

base_url = 'http://edacc3.informatik.uni-ulm.de/SATChallenge2012/'

# competition category - test experiment (id, time limit)  mapping
test_experiments = {
    "Random SAT": (8, 30),
}

try:
    from satchallenge_local_config import *
except:
    pass



