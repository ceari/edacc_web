# -*- coding: utf-8 -*-
"""
    manage
    ------

    Flask-Actions manage script.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

from flask import Flask
from flaskext.actions import Manager
from edacc.web import app

manager = Manager(app)

if __name__ == "__main__":
    manager.run()
