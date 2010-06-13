# -*- coding: utf-8 -*-

from edacc import app
from edacc.constants import JOB_STATUS, JOB_STATUS_COLOR

def download_size(value):
    """ Takes an integer number of bytes and returns a pretty string representation """
    if value <= 0: return "0 Bytes"
    elif value < 1024: return str(value) + " Bytes"
    elif value < 1024*1024: return "%.1f kB" % (value / 1024.0)
    else: return "%.1f MB" % (value / 1024.0 / 1024.0)
    
def job_status(value):
    """ Translates an integer job status to a string pretty representation """
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
    """ returns a string of the solver configuration parameters """
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
    """ returns a string of what the solver launch command looks like given the solver configuration """
    return "./" + solver_config.solver.binaryName + " " + parameter_string(solver_config)

def datetimeformat(value, format='%H:%M / %d-%m-%Y'):
    return value.strftime(format)

app.jinja_env.filters['download_size'] = download_size
app.jinja_env.filters['job_status'] = job_status
app.jinja_env.filters['job_status_color'] = job_status_color
app.jinja_env.filters['launch_command'] = launch_command
app.jinja_env.filters['datetimeformat'] = datetimeformat
