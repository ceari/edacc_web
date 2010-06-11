#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Development server, using Flask's builtin server
    run 'python server.py' from a terminal to launch
"""

from edacc import app
from edacc.config import DEBUG

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=DEBUG)
