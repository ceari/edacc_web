# -*- coding: utf-8 -*-
"""
    edacc.forms
    -----------

    Various WTF-Forms used by the web frontend
"""

from flaskext.wtf import Form, TextField, PasswordField, TextAreaField
from flaskext.wtf import validators

class RegistrationForm(Form):
    lastname = TextField(u'Last Name',
                         [validators.Required(),
                          validators.Length(max=255)])
    firstname = TextField(u'First Name',
                          [validators.Required(),
                           validators.Length(max=255)])
    email = TextField(u'First Name',
                      [validators.Required(),
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
    captcha = TextField('Give a solution')

class LoginForm(Form):
    email = TextField('Email')
    password = TextField('Password')