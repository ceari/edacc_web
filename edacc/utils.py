# -*- coding: utf-8 -*-
"""
    edacc.utils
    -----------

    Utility functions, jinja2 filters, etc.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import random
import struct
from cStringIO import StringIO

import pylzma

from edacc.constants import JOB_STATUS_COLOR, JOB_RESULT_CODE_COLOR

def newline_split_string(s, n):
    """ Splits the string s up into parts of size n and returns
        the concatenation of these parts separated by newline characters
        as result. """
    if n == 0: return s
    return '\n'.join([s[i:i+n] for i in range(0, len(s), n)])

def download_size(value):
    """ Takes an integer number of bytes and returns a pretty string representation """
    if value <= 0: return "0 Bytes"
    elif value < 1024: return str(value) + " Bytes"
    elif value < 1024*1024: return "%.1f kB" % (value / 1024.0)
    else: return "%.1f MB" % (value / 1024.0 / 1024.0)

def job_status_color(value):
    """ Returns an HTML conform color string for the job status """
    if value not in JOB_STATUS_COLOR:
        return 'grey'
    else:
        return JOB_STATUS_COLOR[value]

def job_result_code_color(value):
    """ Returns an HTML conform color string for the job result code """
    if value not in JOB_RESULT_CODE_COLOR:
        return 'grey'
    else:
        return JOB_RESULT_CODE_COLOR[value]

def parameter_string(solver_config):
    """ Returns a string of the solver configuration parameters """
    parameters = solver_config.parameter_instances
    args = []
    for p in parameters:
        args.append(p.parameter.prefix or "")
        if p.parameter.name == 'seed':
            args.append("<seed>")
        if p.parameter.name == 'instance':
            args.append("<instance>")
        if p.parameter.name == 'tempdir':
            args.append("<tempdir>")
        if p.parameter.hasValue:
            if p.value == "": # if value not set, use default value from parameters table
                args.append(p.parameter.defaultValue or "")
            else:
                args.append(p.value or "")
    return " ".join(args)

def parameter_template(solver):
    """ Returns a string of the solver configuration parameters """
    parameters = solver.parameters
    args = []
    for p in parameters:
        if p.prefix: args.append(p.prefix)
        if p.space and p.prefix and p.hasValue: args.append(" ")
        if p.name == 'seed':
            args.append("SEED")
        if p.name == 'tempdir':
            args.append("TEMPDIR")
        if p.name == 'instance':
            args.append("INSTANCE")
        if p.hasValue:
            args.append(p.defaultValue or "")
        args.append(" ")
    return "".join(args)

def result_time(time):
    """ Returns a representation of the time value. If time is None
        a dash character is returned, otherwise the time is returned """
    if time is None:
        return '-'
    else:
        return time

def launch_command(solver_config):
    """ Returns a string of what the solver launch command looks like
    given the solver configuration
    """
    return (solver_config.solver_binary.runCommand or "") + " ./" + (solver_config.solver_binary.runPath or "") + " " + parameter_string(solver_config)

def datetimeformat(value, format='%H:%M, %d-%m-%Y'):
    """ Returns the passed datetime value as formatted string according to the formatting string
    :format:
    """
    if value is None: return ""
    return value.strftime(format)

def competition_phase(value):
    """ Returns a textual label of a competiton phase given by an integer value """
    if value == 1: return "Category Definition Phase"
    elif value == 2: return "Registration and Submission Phase"
    elif value == 3: return "Solver Testing Phase"
    elif value == 4: return "Solver Resubmission Phase"
    elif value == 5: return "Competition Phase"
    elif value == 6: return "Release Phase"
    elif value == 7: return "Post-Release Phase"
    else: return "unknown phase"

def parse_parameters(parameters):
    """ Parse parameters from the solver submission form, returns a list
        of tuples (name, prefix, default_value, boolean, order)
    """
    parameters = parameters.strip().split()
    params = []
    i = 0
    while i < len(parameters):
        if parameters[i].startswith('-') and not "=" in parameters[i]:
            # prefixed parameter
            if i+1 < len(parameters) and (parameters[i+1].lower() in ('seed', 'instance', 'tempdir')):
                pname = parameters[i+1].lower()
                prefix = parameters[i]
                default_value = ''
                boolean = False
                params.append((pname, prefix, default_value, boolean, i, True))
                i += 2
            else:
                pname = parameters[i]
                prefix = parameters[i]
                if i+1 == len(parameters) or parameters[i+1].startswith('-'):
                    boolean = True
                    default_value = ''
                    params.append((pname, prefix, default_value, boolean, i, True))
                    i += 1
                else:
                    boolean = False
                    default_value = parameters[i+1]
                    params.append((pname, prefix, default_value, boolean, i, True))
                    i += 2
        else:
            if "=" in parameters[i] and ("INSTANCE" in parameters[i] or "SEED" in parameters[i] or "TEMPDIR" in parameters[i]):
                pname = parameters[i].split("=")[1].lower()
                prefix = parameters[i].split("=")[0] + "="
                default_value = ''
                boolean = False
                space = False
            else:
                # parameter without prefix
                if parameters[i].lower() in ('seed', 'instance', 'tempdir'):
                    pname = parameters[i].lower()
                    prefix = ''
                    default_value = ''
                    boolean = False
                    space = True
                else:
                    pname = parameters[i]
                    prefix = parameters[i]
                    default_value = ''
                    boolean = True
                    space = True
            params.append((pname, prefix, default_value, boolean, i, space))
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

def formatOutputFile(data):
    if data is not None:
        if len(data) > 4*1024:
            # show only the first and last 2048 characters if the resultFile is larger than 4kB
            resultFile_text = data[:2048] + "\n\n... [truncated " + str(int((len(data) - 4096) / 1024.0)) + " kB]\n\n" + data[-2048:]
        else:
            resultFile_text = data
    else:
        resultFile_text = "No output"
    return resultFile_text

def lzma_decompress(data):
    """
        LZMA decompression using pylzma.
        The LZMA header consists of 5 + 8 bytes.
        The first 5 bytes are compression parameters, the 8 following bytes specify
        the length of the data.
    """
    # unpack the data length from the LZMA header (bytes # 6-13 inclusively/unsigned long long int)
    coded_length = struct.unpack('<Q', data[5:13])[0]
    if coded_length == '\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF':
        # if the length is -1 (in two's complement), there is an EOS marker
        # marking the end of the data and pylzma doesn't need the coded_length
        return pylzma.decompress(data[:5] + data[13:])
    else:
        # if the length is specified, pylzma needs the coded_length since there probably
        # is no EOS marker
        return pylzma.decompress(data[:5] + data[13:], maxlength=coded_length)

def lzma_compress(data):
    """ LZMA compression using pylzma """
    c = pylzma.compressfile(StringIO(data), dictionary=8, fastBytes=128,
                            algorithm=0, eos=0, matchfinder='hc3')
    result = c.read(5)
    result += struct.pack('<Q', len(data))
    return result + c.read()

def truncate_name(s, l=100):
    if len(s) > l:
        return s[:l/2] + " [..] " + s[-l/2:]
    return s