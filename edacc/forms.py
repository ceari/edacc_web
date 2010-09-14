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
    #solver_property = SelectField('Property')
    instances = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance)
    scaling = RadioField('Axes scale', choices=[('none', 'none'), ('log', 'log'),
                                             ('loglog', 'log-log')])
    run = SelectField('Plot for run')

class CactusPlotForm(Form):
    solver_property = SelectField('Property')
    instance_filter = TextField('Filter Instances')
    instances = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance)

class RTDComparisonForm(Form):
    solver_config1 = QuerySelectField('First Solver Configuration')
    solver_config2 = QuerySelectField('Second Solver Configuration')
    instance = QuerySelectField('Instance', get_pk=lambda i: i.idInstance)
    instance_filter = TextField('Filter Instances')