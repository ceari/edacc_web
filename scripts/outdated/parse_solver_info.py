""" Parse solver info from the SAT Competition 09 website.
    To be used after the import script.
"""
import sys, urllib2
sys.path.append("..")
from BeautifulSoup import BeautifulSoup

from edacc import models, config
config.DATABASE_HOST = "localhost"
models.add_database("edacc", "passw", "EDACC5", "EDACC5")
db = models.get_database("EDACC5")

html_url = raw_input('Enter solverlist url (e.g. http://www.cril.univ-artois.fr/SAT09/results/solverlist.php?idev=22): ')
p = urllib2.urlopen(html_url)
soup = BeautifulSoup(p.read())

for solver_tab in soup.findAll('table'):
    if not solver_tab.find('td', text='Event'): continue
    version = solver_tab.find('td', attrs={"class": "fieldname"}, text='Version').findNext('td').string.strip()
    name = solver_tab.find('td', attrs={"class": "fieldname"}, text='Name').findNext('td').string.strip()
    authors = solver_tab.find('td', attrs={"class": "fieldname"}, text='Authors').findNext('td').string.strip()
    description = solver_tab.find('td', attrs={"class": "fieldname"}, text='Comments').findNext('td').contents
    description = map(lambda e: '\n' if str(e) == '<br />' else e, description)

    solver = db.session.query(db.Solver).filter_by(name=name,version=version).first()
    if solver:
        solver.authors = authors
        db.session.commit()
    else:
        print "Didn't find", name, version, " in the DB, skipping"
