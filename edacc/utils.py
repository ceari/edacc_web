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
    
    
app.jinja_env.filters['download_size'] = download_size
app.jinja_env.filters['job_status'] = job_status
app.jinja_env.filters['job_status_color'] = job_status_color