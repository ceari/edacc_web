# -*- coding: utf-8 -*-
"""
    edacc.forms
    -----------

    Various WTForms used by the web frontend.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

from flaskext.wtf import Form, TextField, PasswordField, TextAreaField, RadioField
from flaskext.wtf import FileField, Required, Length, Email, EqualTo, SelectField
from flaskext.wtf import ValidationError
from wtforms.ext.sqlalchemy.fields import QuerySelectMultipleField,\
                                            QuerySelectField

ERROR_REQUIRED = 'This field is required.'

class EmptyQuery(list):
    """ Helper class that extends the builtin list class to always evaluate to
        True.
        WTForms tries to iterate over field.query or field.query_factory(). But
        when field.query an empty list and evaluates to False, field.query_factory
        returns None and causes an exception. """
    def __nonzero__(self):
        """ for Python 2.x """
        return True
    def __bool__(self):
        """ for Python 3.x """
        return True


class RegistrationForm(Form):
    lastname = TextField('Last Name',
                         [Required(ERROR_REQUIRED),
                          Length(max=255)])
    firstname = TextField('First Name',
                          [Required(ERROR_REQUIRED),
                           Length(max=255)])
    email = TextField('Email',
                      [Required(ERROR_REQUIRED),
                       Length(max=255),
                       Email(message='Invalid e-mail address.')])
    password = PasswordField('Password',
                             [Required()])
    password_confirm = PasswordField('Confirm Password',
                                     [EqualTo('password',
                                        message='Passwords must match.')])
    address = TextAreaField('Postal Address')
    affiliation = TextAreaField('Affiliation')
    captcha = TextField()

class LoginForm(Form):
    email = TextField('Email', [Required(ERROR_REQUIRED)])
    password = PasswordField('Password',
                             [Required(ERROR_REQUIRED)])

class SolverForm(Form):
    name = TextField('Name', [Required(ERROR_REQUIRED)])
    binary = FileField('Binary')
    code = FileField('Code')
    description = TextAreaField('Description')
    version = TextField('Version', [Required(ERROR_REQUIRED)])
    authors = TextField('Authors', [Required(ERROR_REQUIRED)])
    parameters = TextField('Parameters', [Required(ERROR_REQUIRED)])
    competition_categories = QuerySelectMultipleField(
                                'Competition Categories',
                                query_factory=lambda: [],
                                validators=[Required('Please choose one or more \
                                                     categories for your solver \
                                                     to compete in.')])

    def validate_parameters(form, field):
        if not 'SEED' in field.data or not 'INSTANCE' in field.data:
            raise ValidationError('You have to specify SEED \
                                             and INSTANCE as parameters.')

    def validate_code(form, field):
        if not field.file.filename or not field.file.filename.endswith('.zip'):
            raise ValidationError('The code archive has to be a .zip file.')

class BenchmarkForm(Form):
    instance = FileField('File')
    name = TextField('Name')
    new_benchmark_type = TextField('New Type')
    benchmark_type = QuerySelectField('Existing Type', allow_blank=True,
                                      query_factory=lambda: [],
                                      blank_text='Create a new type')
    new_source_class = TextField('New Source Class')
    new_source_class_description = TextField('New Source Class Description')
    source_class = QuerySelectField('Exisiting Source Class', allow_blank=True,
                                    query_factory=lambda: [],
                                    blank_text='Create a new source class')

    def validate_new_benchmark_type(form, field):
        if form.benchmark_type.data is None and field.data.strip() == '':
            raise ValidationError('Please specify a new benchmark type or choose \
                                  an existing one.')

    def validate_new_source_class(form, field):
        if form.source_class.data is None and field.data.strip() == '':
            raise ValidationError('Please specify a new source class or choose \
                                  an existing one.')

    def validate_instance(form, field):
        if not field.file.filename:
            raise ValidationError(ERROR_REQUIRED)

class ResultBySolverForm(Form):
    solver_config = QuerySelectField('Solver Configuration')

class ResultByInstanceForm(Form):
    instance = QuerySelectField('Instance', get_pk=lambda i: i.idInstance)

class TwoSolversOnePropertyScatterPlotForm(Form):
    solver_config1 = QuerySelectField('First Solver Configuration')
    solver_config2 = QuerySelectField('Second Solver Configuration')
    instance_filter = TextField('Filter Instances')
    result_property = SelectField('Property')
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    xscale = RadioField('X-axis scale', choices=[('', 'linear'), ('log', 'log')], default='')
    yscale = RadioField('Y-axis scale', choices=[('', 'linear'), ('log', 'log')], default='')
    run = SelectField('Plot for run')

class OneSolverTwoResultPropertiesPlotForm(Form):
    solver_config = QuerySelectField('Solver Configuration')
    result_property1 = SelectField('First Result Property')
    result_property2 = SelectField('Second Result Property')
    instance_filter = TextField('Filter Instances')
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    xscale = RadioField('X-axis scale', choices=[('', 'linear'), ('log', 'log')], default='')
    yscale = RadioField('Y-axis scale', choices=[('', 'linear'), ('log', 'log')], default='')
    run = SelectField('Plot for run')

class OneSolverInstanceAgainstResultPropertyPlotForm(Form):
    solver_config = QuerySelectField('Solver Configuration')
    result_property = SelectField('Result Property')
    instance_property = SelectField('Instance Property')
    instance_filter = TextField('Filter Instances')
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    xscale = RadioField('X-axis scale', choices=[('', 'linear'), ('log', 'log')], default='')
    yscale = RadioField('Y-axis scale', choices=[('', 'linear'), ('log', 'log')], default='')
    run = SelectField('Plot for run')

class CactusPlotForm(Form):
    result_property = SelectField('Property')
    sc = QuerySelectMultipleField('Solver Configurations')
    instance_filter = TextField('Filter Instances')
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)

class RTDComparisonForm(Form):
    solver_config1 = QuerySelectField('First Solver Configuration')
    solver_config2 = QuerySelectField('Second Solver Configuration')
    result_property = SelectField('Property')
    instance = QuerySelectField('Instance', get_pk=lambda i: i.idInstance, allow_blank=True)
    instance_filter = TextField('Filter Instances')

class RTDPlotsForm(Form):
    sc = QuerySelectMultipleField('Solver Configurations')
    result_property = SelectField('Property')
    instance = QuerySelectField('Instance', get_pk=lambda i: i.idInstance, allow_blank=True)
    instance_filter = TextField('Filter Instances')

class RTDPlotForm(Form):
    solver_config = QuerySelectField('Solver Configuration')
    result_property = SelectField('Property')
    instance = QuerySelectField('Instance', get_pk=lambda i: i.idInstance, allow_blank=True)
    instance_filter = TextField('Filter Instances')

class ProbabilisticDominationForm(Form):
    result_property = SelectField('Property')
    solver_config1 = QuerySelectField('First Solver Configuration')
    solver_config2 = QuerySelectField('Second Solver Configuration')

class BoxPlotForm(Form):
    solver_configs = QuerySelectMultipleField('Solver Configurations')
    result_property = SelectField('Property')
    instances = QuerySelectMultipleField('Instances')
    instance_filter = TextField('Filter Instances')
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)

class RankingForm(Form):
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    instance_filter = TextField('Filter Instances')