# -*- coding: utf-8 -*-
"""
    edacc.forms
    -----------

    Various WTForms used by the web frontend.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

from flaskext.wtf import Form, TextField, PasswordField, TextAreaField
from flaskext.wtf import FileField, Required, Length, Email, EqualTo
from flaskext.wtf import ValidationError
from wtforms.ext.sqlalchemy.fields import QuerySelectField

class RegistrationForm(Form):
    lastname = TextField('Last Name',
                         [Required('This field is required.'),
                          Length(max=255)])
    firstname = TextField('First Name',
                          [Required('This field is required.'),
                           Length(max=255)])
    email = TextField('Email',
                      [Required('This field is required.'),
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
    email = TextField('Email', [Required('This field is required.')])
    password = PasswordField('Password',
                             [Required('This field is required.')])

class SolverForm(Form):
    name = TextField('Name', [Required('This field is required.')])
    binary = FileField('Binary')
    code = FileField('Code')
    description = TextAreaField('Description')
    version = TextField('Version', [Required('This field is required.')])
    authors = TextField('Authors', [Required('This field is required.')])
    parameters = TextField('Parameters', [Required('This field is required.')])
    

    def validate_parameters(form, field):
        if not 'SEED' in field.data or not 'INSTANCE' in field.data:
            raise ValidationError('You have to specify SEED \
                                             and INSTANCE as parameters.')

    def validate_code(form, field):
        if not field.file.filename or not field.file.filename.endswith('.zip'):
            raise ValidationError('The code archive has to be a .zip file.')

class BenchmarkForm(Form):
    pass