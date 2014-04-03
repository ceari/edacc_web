DB_NAME = "EDACC"
DB_USER = "edacc"
DB_PASSWORD = "pw"

base_url = 'http://URL/'

# competition category - test experiment (id, cpu time limit, wall time limit, memory limit)  mapping
test_experiments = {
    "Random SAT": (8, 30 -1, -1),
}

try:
    from sc14_local_config import *
except:
    pass



