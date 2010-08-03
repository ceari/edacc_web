# -*- coding: utf-8 -*-
"""
    edacc.forms
    -----------

    Various WTForms used by the web frontend.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

from flaskext.wtf import Form, TextField, PasswordField, TextAreaField
from flaskext.wtf import FileField
from flaskext.wtf import validators

class RegistrationForm(Form):
    lastname = TextField(u'Last Name',
                         [validators.Required(u'Required'),
                          validators.Length(max=255)])
    firstname = TextField(u'First Name',
                          [validators.Required(u'Required'),
                           validators.Length(max=255)])
    email = TextField(u'Email',
                      [validators.Required(u'Required'),
                       validators.Length(max=255),
                       validators.Email(message='Invalid e-mail address')])
    password = PasswordField('Password',
                             [validators.Required(),
                              validators.EqualTo('password_confirm',
                                                 message='Passwords must match')
                              ])
    password_confirm = PasswordField('Confirm Password')
    address = TextAreaField('Postal Address')
    affiliation = TextAreaField('Affiliation')
    captcha = TextField()

class LoginForm(Form):
    email = TextField('Email', [validators.Required(u'required')])
    password = PasswordField('Password', [validators.Required(u'required')])

class SolverForm(Form):
    name = TextField(u'Name')
    binary = FileField(u'Binary')
    code = FileField(u'Binary')
    description = TextAreaField(u'Description')
    version = TextField(u'Version')
    authors = TextField(u'Authors')
    parameters = TextField('Parameters')

class BenchmarkForm(Form):
    pass