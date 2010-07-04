# -*- coding: utf-8 -*-

# Enable or disable printing of debug messages
DEBUG = True

# Enable or disable memcached usage to cache expensive calculation results
CACHING = False
# Cache timeout in seconds
CACHE_TIMEOUT = 5
# Host and port of the memcache daemon
MEMCACHED_HOST = '127.0.0.1:11211'

TEMP_DIR = '/tmp/'

LOG_FILE = '/srv/edacc_web/error.log'

# Key used for signing cookies and salting crytpographic hashes. This has to be kept secret.
# It is impossible to authenticate stored passwords if this key differs from the one used to create the password hashes.
SECRET_KEY = '\xb4\xd5\xcd"\xd2Tm\xc4x*O:1\x85\x83\xf1\xf5\rc\xfc\xf8\xd0#|\xa5\xd8\xb1nM\xd9D\x97^\xb9M}e_\xb9az\xd5@\x7f\xadtLb\t\x9a\x85TJ\xf6\x1d\x92)1\x83\x17h\xbd\xfe\xc1\xa5\xe2\xae\xf0\xc8\x0c\xb8\xda7A\xab\xcc\xb2j\x13tz\xce\xa7a\xa8\xdcv\x9d$\xe9.\xd1\xd7\xf3U?AN\xf7\xa3'

DATABASE_DRIVER     = 'mysql'
DATABASE_HOST       = 'localhost'
DATABASE_PORT       = 3306

# Used to log into the admin interface
ADMIN_PASSWORD = 'affe42'

# List of databases this server connects to at startup
# Format: Tuples of username, password, database, label (used on the pages)
DEFAULT_DATABASES = (
    ('edacc', 'edaccteam', 'EDACC', 'Competition'),
    ('edacc', 'edaccteam', 'EDACC3', 'Webtest'),
)