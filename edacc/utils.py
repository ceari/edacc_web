# -*- coding: utf-8 -*-

import random
from edacc.web import app
from edacc.constants import JOB_STATUS, JOB_STATUS_COLOR

def download_size(value):
    """ Takes an integer number of bytes and returns a pretty string representation """
    if value <= 0: return "0 Bytes"
    elif value < 1024: return str(value) + " Bytes"
    elif value < 1024*1024: return "%.1f kB" % (value / 1024.0)
    else: return "%.1f MB" % (value / 1024.0 / 1024.0)
    
def job_status(value):
    """ Translates an integer job status to its string representation """
    if value not in JOB_STATUS:
        return "unknown status"
    else:
        return JOB_STATUS[value]
    
def job_status_color(value):
    """ Returns an HTML conform color string for the job status """
    if value not in JOB_STATUS:
        return ''
    else:
        return JOB_STATUS_COLOR[value]
        
def parameter_string(solver_config):
    """ Returns a string of the solver configuration parameters """
    parameters = solver_config.parameter_instances
    args = []
    for p in parameters:
        args.append(p.parameter.prefix)
        if p.parameter.hasValue:
            if p.value == "": # if value not set, use default value from parameters table
                args.append(p.parameter.value)
            else:
                args.append(p.value)
    return " ".join(args)
        
def launch_command(solver_config):
    """ Returns a string of what the solver launch command looks like given the solver configuration """
    return "./" + solver_config.solver.binaryName + " " + parameter_string(solver_config)

def datetimeformat(value, format='%H:%M / %d-%m-%Y'):
    return value.strftime(format)
    
def competition_phase(value):
    """ returns a textual label of a competiton phase given by an integer value """
    if value == 1: return "Submission phase"
    elif value == 2: return "Experiment creation phase"
    elif value == 3: return "Competition/Tests running"
    elif value == 4: return "Competition finished"
    else: return "unknown phase"
    

app.jinja_env.filters['download_size'] = download_size
app.jinja_env.filters['job_status'] = job_status
app.jinja_env.filters['job_status_color'] = job_status_color
app.jinja_env.filters['launch_command'] = launch_command
app.jinja_env.filters['datetimeformat'] = datetimeformat
app.jinja_env.filters['competition_phase'] = competition_phase

def parse_parameters(parameters):
    """ Parse parameters from the solver submission form, returns a list
        of tuples (name, prefix, default_value, boolean, order) """
    parameters = parameters.strip().split()
    params = []
    i = 0
    while i < len(parameters):
        if parameters[i].startswith('-'):
            # prefixed parameter
            if i+1 < len(parameters) and (parameters[i+1] == 'SEED' or parameters[i+1] == 'INSTANCE'):
                pname = parameters[i+1].lower()
                prefix = parameters[i]
                default_value = ''
                boolean = False
                params.append((pname, prefix, default_value, boolean, i))
                i += 2
            else:
                pname = parameters[i]
                prefix = parameters[i]
                if i+1 == len(parameters) or parameters[i+1].startswith('-'):
                    boolean = True
                    default_value = ''
                    params.append((pname, prefix, default_value, boolean, i))
                    i += 1
                else:
                    boolean = False
                    default_value = parameters[i+1]
                    params.append((pname, prefix, default_value, boolean, i))
                    i += 2
        else:
            # parameter without prefix
            if parameters[i] == 'SEED' or parameters[i] == 'INSTANCE':
                pname = parameters[i].lower()
                prefix = ''
                default_value = ''
                boolean = False
            else:
                pname = parameters[i]
                prefix = parameters[i]
                default_value = ''
                boolean = True
            params.append((pname, prefix, default_value, boolean, i))
            i += 1
    return params

# some SAT functions
random.seed()
def random_clause(l):
    return [random.randint(0, 1) for _ in xrange(l)]
    
def random_formula(clauses, clauseLength):
    return [random_clause(clauseLength) for _ in xrange(clauses)]

def assignment(n):
    if n == 1:
        yield [0]
        yield [1]
    else:
        for a in assignment(n - 1):
            yield a + [0]
            yield a + [1]
            
def satisfies(a, f):
    sat_clauses = 0
    for clause in f:
        for i in xrange(len(clause)):
            if clause[i] == a[i]: sat_clauses += 1; break
    if sat_clauses == len(f):
        return True
    return False
        
def SAT(f):
    for a in assignment(len(f[0])):
        if satisfies(a, f): return a
    return None

def render_formula(f):
    res = []
    for c in f:
        cl = []
        for i in xrange(len(c)):
            if c[i] == 0: cl.append(u'\u00ac' + chr(i + ord('A')))
            else: cl.append(chr(i + ord('A')))
        res.append('(' + u' \u2228 '.join(cl) + ')')
    return u' \u2227 '.join(res)

app.jinja_env.filters['render_formula'] = render_formula
