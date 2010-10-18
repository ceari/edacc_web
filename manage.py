# manage.py
# -*- encoding:utf-8 -*-

from flask import Flask
from flaskext.actions import Manager
from edacc.web import app
from edacc import models
import re

manager = Manager(app)

def add_property(app):
    def action(db_name=('db','EDACC'), propertyType=('type', 0),
               propertySource=('source', 0), name=('name', ''), description=('desc', ''),
               regExp=('regExp', ''), value_type=('value_type', ''),
               multiple=('multiple', 0)):
        """Add a new property to the database.

        propertyType: Instance = 0, Result = 1
        propertySource: Instance = 0, InstanceName = 1, LauncherOutput = 2, Parameter = 3, SolverOutput = 4, VerifierOutput = 5, WatcherOutput = 6
        value_type: name of a PropertyValueType
        multiple: multiple occurences 1/0 for true/false

        Arguments in order:
        """
        db = models.get_database(db_name)

        p = db.session.query(db.Property).filter_by(name=name).first()
        if p is None:
            p = db.Property()
        p.propertyType = int(propertyType)
        p.propertySource = int(propertySource)
        p.name = name
        p.description = description
        p.regExpression = regExp
        p.propertyValueType = value_type
        p.isDefault = True
        p.multipleOccourence = int(multiple)
        db.session.add(p)
        try:
            db.session.commit()
            print "Property saved."
        except Exception as e:
            print "Couldn't save property to database:", e
            db.session.rollback()
    return action

def add_value_type(app):
    def action(db_name=('db','EDACC'), name=('name', ''), file_path=('filename', '')):
        """Add a new property value type to the database.
        Arguments in order:
        """
        db = models.get_database(db_name)

        p = db.session.query(db.PropertyValueType).filter_by(name=name).first()
        if p is None:
            p = db.PropertyValueType()

        import os
        try:
            p.typeClass = file(file_path, 'rb').read()
        except Exception as e:
            print "Couldn't open file:", e
            return

        p.name = name
        p.typeClassFileName = os.path.basename(file_path)
        p.isDefault = True
        db.session.add(p)
        try:
            db.session.commit()
            print "Property value type saved."
        except Exception as e:
            print "Couldn't save property value type to database:", e
            db.session.rollback()
    return action

def calculate_instance_properties(app):
    def action(db_name=('db','EDACC')):
        db = models.get_database(db_name)
        instances = db.session.query(db.Instance).all()

        for p in db.session.query(db.Property).filter_by(propertyType=0):
            pat = re.compile(p.regExpression)
            for instance in instances:
                for pv in instance.properties:
                    if pv.property == p:
                        db.session.delete(pv)
                        db.session.commit()
                        break

                if p.propertySource == 0:
                    text = instance.instance
                elif p.propertySource == 1:
                    text = instance.name

                m = re.search(pat, text)
                if m is not None:
                    val = m.groups()[-1]
                    pv = db.InstanceProperties()
                    pv.property = p
                    pv.instance = instance
                    pv.value = val
                    db.session.add(pv)

        try:
            db.session.commit()
            print "Instance property values calculated."
        except Exception as e:
            print "Error while saving instance property values", e
            db.session.rollback()
    return action

def calculate_result_properties(app):
    def action(db_name=('db','EDACC'), experiment=('experiment', '')):
        """Calculate result properties for the jobs of the experiment with the name passed in."""
        db = models.get_database(db_name)
        exp = db.session.query(db.Experiment).filter_by(name=experiment).first()
        if exp is None:
            print "Experiment doesn't exist"
            return

        props = db.session.query(db.Property).filter_by(propertyType=1)
        for p in props:
            pat = re.compile(p.regExpression)
            for result in db.session.query(db.ExperimentResult).filter(db.ExperimentResult.resultCode.like('1%')).filter_by(experiment=exp).all():
                for pv in result.properties:
                    if pv.property == p:
                        for pvv in pv.values:
                            db.session.delete(pvv)
                        db.session.commit()
                        db.session.delete(pv)
                        db.session.commit()

                if p.propertySource == 2:
                    output = result.launcherOutput
                elif p.propertySource == 4:
                    output = result.solverOutput
                elif p.propertySource == 5:
                    output = result.verifierOutput
                elif p.propertySource == 6:
                    output = result.watcherOutput

                m = re.search(pat, output)

                if m is not None:
                    val = m.groups()[-1]
                    pv = db.ExperimentResultProperty()
                    pv.property = p
                    pv.experiment_result = result
                    db.session.add(pv)
                    db.session.flush()
                    pvv = db.ResultPropertyValue()
                    pvv.value = val
                    pvv.order = 0
                    pvv.experiment_result_property = pv
                    db.session.add(pvv)

        try:
            db.session.commit()
            print "Result property values calculated."
        except Exception as e:
            print "Error while saving result property values"
            db.session.rollback()
    return action

manager.add_action('add_property', add_property)
manager.add_action('add_value_type', add_value_type)
manager.add_action('calculate_result_properties', calculate_result_properties)
manager.add_action('calculate_instance_properties', calculate_instance_properties)


if __name__ == "__main__":
    manager.run()
