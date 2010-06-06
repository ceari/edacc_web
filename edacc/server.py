#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.append('..')       # development only

from edacc import app
from edacc.config import DEBUG

app.run(debug=DEBUG)

