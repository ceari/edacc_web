import tempfile
import os
import subprocess
import resource
from itertools import combinations, izip

from edacc import config

sets_union = lambda sets: reduce(lambda x,y: x.union(y), sets, set())

def min_set_cover(U, sets):
    # brute force implementation ...
    min_combinations = list()
    for size in range(1, len(sets)+1):
        for comb in combinations(sets, size):
            if len(U.difference(sets_union(comb))) == 0:
                if comb not in min_combinations:
                    min_combinations.append(comb)
        if min_combinations: break
    return min_combinations

def ak_min_set_cover(U, sets, set_ids):
    def setlimits():
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))

    tempdir = tempfile.mkdtemp()
    with open(os.path.join(tempdir, "instance"), "w") as instance:
        instance.write(' '.join(map(str, sorted(U))) + '\n')
        for sc_id, s in izip(set_ids, sets):
            instance.write(str(sc_id) + ' ' + ' '.join(map(str, sorted(s))) + '\n')

    with open(os.path.join(tempdir, "solution"), "w") as solution:
        solver = subprocess.Popen([os.path.join(config.CONTRIB_DIR, 'setcover/akmaxsat'),
                                   os.path.join(tempdir, "instance")], stdout=subprocess.PIPE, preexec_fn=setlimits)
        solution.write(solver.communicate()[0])

    sol = subprocess.Popen([os.path.join(config.CONTRIB_DIR, 'setcover/verify_msc'), os.path.join(tempdir, "instance"),
                            os.path.join(tempdir, "solution")], stdout=subprocess.PIPE, preexec_fn=setlimits)
    output = sol.communicate()[0]
    min_sets = []
    for line in output.splitlines():
        min_sets.append(map(int, line.split()))

    return min_sets