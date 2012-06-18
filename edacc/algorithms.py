from itertools import combinations

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