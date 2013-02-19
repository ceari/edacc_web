# -*- coding: utf-8 -*-
"""
    edacc.forms
    -----------

    Various WTForms used by the web frontend.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

from flask.ext.wtf import Form, TextField, PasswordField, TextAreaField, RadioField, DecimalField, FloatField
from flask.ext.wtf import FileField, Required, Length, Email, EqualTo, SelectField, IntegerField
from flask.ext.wtf import ValidationError, BooleanField, validators
from wtforms.ext.sqlalchemy.fields import QuerySelectMultipleField,\
                                            QuerySelectField

ERROR_REQUIRED = 'This field is required.'

MAX_SC_LEN = 100 # maximum length of solver config names to display before truncating

def truncate_name(s, l):
    if len(s) > l:
        return s[:l/2] + " [..] " + s[-l/2:]
    return s

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
    firstname = TextField('Given Name',
                          [Required(ERROR_REQUIRED),
                           Length(max=255)])
    email = TextField('e-mail',
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
    accepted_terms = BooleanField('I have read, understood and accepted the terms and conditions.', [Required(ERROR_REQUIRED)])
    captcha = TextField()

class LoginForm(Form):
    email = TextField('e-mail', [Required(ERROR_REQUIRED)])
    password = PasswordField('Password',
                             [Required(ERROR_REQUIRED)])
    permanent_login = BooleanField('Remember me')

class ChangePasswordForm(Form):
    password = PasswordField('Password',
        [Required()])
    password_confirm = PasswordField('Confirm Password',
        [EqualTo('password',
            message='Passwords must match.')])

class ResetPasswordForm(Form):
    email = TextField('e-mail', [Required(ERROR_REQUIRED)])

class SolverForm(Form):
    name = TextField('Name', [Required(ERROR_REQUIRED)])
    binary = FileField('Binary')
    code = FileField('Code')
    description = TextAreaField('Description')
    description_pdf = FileField('Description (PDF)')
    version = TextField('Version', [Required(ERROR_REQUIRED)])
    run_path = TextField('Binary name')
    run_command = TextField('Run command')
    authors = TextField('Authors', [Required(ERROR_REQUIRED)])
    parameters = TextField('Parameters', [Required(ERROR_REQUIRED)])
    competition_categories = QuerySelectMultipleField(
                                'Competition Categories',
                                query_factory=lambda: [],
                                validators=[Required('Please choose one or more \
                                                     categories for your solver \
                                                     to compete in.')])

    def validate_parameters(self, field):
        if not 'INSTANCE' in field.data:
            raise ValidationError('You have to specify INSTANCE as a parameter.')

    def validate_code(self, field):
        if field.data and not field.file.filename.endswith('.zip'):
            raise ValidationError('The code archive has to be a .zip file.')

    def validate_description_pdf(self, field):
        if field.data and not field.file.filename.endswith('.pdf'):
            raise ValidationError('Please provide a .pdf file.')

class UpdateDescriptionForm(Form):
    description_pdf = FileField('Description (PDF)')

    def validate_description_pdf(self, field):
        if field.data and not field.file.filename.endswith('.pdf'):
            raise ValidationError('Please provide a .pdf file.')

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

    def validate_new_benchmark_type(self, field):
        if self.benchmark_type.data is None and field.data.strip() == '':
            raise ValidationError('Please specify a new benchmark type or choose \
                                  an existing one.')

    def validate_new_source_class(self, field):
        if self.source_class.data is None and field.data.strip() == '':
            raise ValidationError('Please specify a new source class or choose \
                                  an existing one.')

    def validate_instance(self, field):
        if not field.file.filename:
            raise ValidationError(ERROR_REQUIRED)

class BenchmarksForm(Form):
    #benchmarks = FileField('File')
    category = SelectField('Category', [Required(ERROR_REQUIRED)],
        choices=[('random', 'Random SAT+UNSAT'), ('random_sat', 'Random SAT'), ('random_unsat', 'Random UNSAT'),
        ('application', 'Application SAT+UNSAT'), ('application_sat', 'Application SAT'), ('application_unsat', 'Application UNSAT'),
        ('combinatorial', 'Hard Combinatorial SAT+UNSAT'), ('combinatorial_sat', 'Hard Combinatorial SAT'), ('combinatorial_unsat', 'Hard Combinatorial UNSAT')],
        default='random')

    #def validate_benchmarks(self, field):
    #    if not field.file.filename:
    #        raise ValidationError(ERROR_REQUIRED)
    #    filename = field.file.filename
    #    if not (filename.endswith('.zip') or filename.endswith('.7z') or filename.endswith('.tar.gz') \
    #        or filename.endswith('.tar.bz2') or filename.endswith('.rar')):
    #        raise ValidationError("Please submit one of the supported archive types.")

class ResultBySolverForm(Form):
    solver_config = QuerySelectField('Solver Configuration', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    cost = SelectField('Cost', choices = [('resultTime', 'CPU Time'), ('wallTime', 'Walltime'), ('cost', 'Cost')])

class ResultByInstanceForm(Form):
    instance = QuerySelectField('Instance', get_pk=lambda i: i.idInstance)
    cost = SelectField('Cost', choices = [('resultTime', 'CPU Time'), ('wallTime', 'Walltime'), ('cost', 'Cost')])

class TwoSolversOnePropertyScatterPlotForm(Form):
    solver_config1 = QuerySelectField('First Solver Configuration', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    solver_config2 = QuerySelectField('Second Solver Configuration', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    instance_filter = TextField('Filter Instances')
    result_property = SelectField('Property')
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    xscale = RadioField('X-axis scale', choices=[('', 'linear'), ('log', 'log')], default='log')
    yscale = RadioField('Y-axis scale', choices=[('', 'linear'), ('log', 'log')], default='log')
    run = SelectField('Plot for run')

class OneSolverTwoResultPropertiesPlotForm(Form):
    solver_config = QuerySelectField('Solver Configuration', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    result_property1 = SelectField('First Result Property')
    result_property2 = SelectField('Second Result Property')
    instance_filter = TextField('Filter Instances')
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    xscale = RadioField('X-axis scale', choices=[('', 'linear'), ('log', 'log')], default='log')
    yscale = RadioField('Y-axis scale', choices=[('', 'linear'), ('log', 'log')], default='log')
    run = SelectField('Plot for run')

class OneSolverInstanceAgainstResultPropertyPlotForm(Form):
    solver_config = QuerySelectField('Solver Configuration', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    result_property = SelectField('Result Property')
    instance_property = SelectField('Instance Property')
    instance_filter = TextField('Filter Instances')
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    xscale = RadioField('X-axis scale', choices=[('', 'linear'), ('log', 'log')], default='log')
    yscale = RadioField('Y-axis scale', choices=[('', 'linear'), ('log', 'log')], default='log')
    run = SelectField('Plot for run')

class CactusPlotForm(Form):
    result_property = SelectField('Property')
    sc = QuerySelectMultipleField('Solver Configurations')
    instance_filter = TextField('Filter Instances')
    run = SelectField('Plot for run')
    flip_axes = BooleanField("Swap axes", default=True)
    log_property = BooleanField("Logarithmic property-axis", default=True)
    i = QuerySelectMultipleField('Instances (Group 0)', get_pk=lambda i: i.idInstance, allow_blank=True)

class RTDComparisonForm(Form):
    solver_config1 = QuerySelectField('First Solver Configuration', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    solver_config2 = QuerySelectField('Second Solver Configuration', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    result_property = SelectField('Property')
    log_property = BooleanField("Logarithmic property-axis", default=True)
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    instance_filter = TextField('Filter Instances')

class RTDPlotsForm(Form):
    sc = QuerySelectMultipleField('Solver Configurations', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    result_property = SelectField('Property')
    log_property = BooleanField("Logarithmic property-axis", default=True)
    instance = QuerySelectField('Instance', get_pk=lambda i: i.idInstance, allow_blank=True)
    instance_filter = TextField('Filter Instances')

class RTDPlotForm(Form):
    #solver_config = QuerySelectField('Solver Configuration', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    sc = QuerySelectMultipleField('Solver Configurations', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    result_property = SelectField('Property')
    log_property = BooleanField("Logarithmic property-axis", default=True)
    restart_strategy = BooleanField(u"Show restart strategy (t_rs, green=original mean, blue=mean with restarts, red=restart at)")
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    instance_filter = TextField('Filter Instances')

class ProbabilisticDominationForm(Form):
    result_property = SelectField('Property')
    solver_config1 = QuerySelectField('First Solver Configuration', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    solver_config2 = QuerySelectField('Second Solver Configuration', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    instance_filter = TextField('Filter Instances')
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)

class BoxPlotForm(Form):
    solver_configs = QuerySelectMultipleField('Solver Configurations', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    result_property = SelectField('Property')
    instances = QuerySelectMultipleField('Instances')
    instance_filter = TextField('Filter Instances')
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)

class RankingForm(Form):
    i = QuerySelectMultipleField('Instances', get_label=lambda i: i.get_name(), get_pk=lambda i: i.idInstance, allow_blank=True)
    calculate_average_dev = BooleanField('Calculate dispersion measures', default=False)
    penalized_average_runtime = BooleanField('Calculate penalized average cost', default=False)
    median_runtime = BooleanField('Calculate penalized median cost', default=False)
    par_factor = IntegerField('Penalty factor', default=1)
    careful_ranking = BooleanField("Calculate careful ranking", default=False)
    careful_ranking_noise = FloatField("Noise", default=1.0, validators=[validators.required()])
    survnoise = FloatField("Noise", default=0.0, validators=[validators.required()])
    survival_ranking_alpha = FloatField("alpha", default=0.05, validators=[validators.required()])
    survival_ranking = BooleanField("Calculate survival ranking", default=False)
    break_careful_ties = BooleanField('Break careful ranking ties', default=False)
    instance_filter = TextField('Filter Instances')
    cost = SelectField('Cost', choices = [('resultTime', 'CPU Time'), ('wallTime', 'Walltime'), ('cost', 'Cost')])
    property_limit = FloatField("Property limit (for result properties)", default=1.0, validators=[validators.required()])
    show_top = IntegerField("Maximum number of configurations displayed", default=1000)

class SOTAForm(Form):
    sc = QuerySelectMultipleField('Solver Configurations', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    i = QuerySelectMultipleField('Instances', get_label=lambda i: i.get_name(), get_pk=lambda i: i.idInstance, allow_blank=True)
    cost = SelectField('Cost', choices = [('resultTime', 'CPU Time'), ('wallTime', 'Walltime'), ('cost', 'Cost')])
    instance_filter = TextField('Filter Instances')

class ResultsBySolverAndInstanceForm(Form):
    solver_configs = QuerySelectMultipleField('Solver Configurations', get_label=lambda sc: truncate_name(sc.name, MAX_SC_LEN))
    cost = SelectField('Cost', choices = [('resultTime', 'CPU Time'), ('wallTime', 'Walltime'), ('cost', 'Cost')])
    display_measure = SelectField('Display measure', default='par10',
                                  choices=[('mean', 'mean'), ('median', 'median'),
                                    ('par10', 'par10'), ('min', 'min'), ('max', 'max'), ('par1', 'par1')])
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    instance_filter = TextField('Filter Instances')
    calculate_dispersion = BooleanField('Calculate dispersion measures', default=False)
    
class RuntimeMatrixPlotForm(Form):
    measure = SelectField('Measure', default='par10',
                                  choices=[('mean', 'mean'),
                                    ('par10', 'par10'), ('min', 'min'), ('max', 'max')])
    result_property = SelectField('Result property', choices = [('resultTime', 'CPU Time'), ('wallTime', 'Walltime'), ('cost', 'Cost')])

class ParameterPlot2DForm(Form):
    parameter1 = SelectField('First parameter')
    parameter2 = SelectField('Second parameter')
    log_x = BooleanField("Logarithmic x-axis")
    log_y = BooleanField("Logarithmic y-axis")
    log_cost = BooleanField("Logarithmic cost")
    measure = SelectField('Measure', default='par10',
        choices=[('mean', 'mean'), ('median', 'median'),
            ('par10', 'par10'), ('min', 'min'), ('max', 'max')])
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    instance_filter = TextField('Filter Instances')
    surface_interpolation = BooleanField("Interpolate surface", default=True)

class ParameterPlot1DForm(Form):
    parameter = SelectField('First parameter')
    log_x = BooleanField("Logarithmic parameter-axis")
    log_y = BooleanField("Logarithmic cost-axis")
    measure = SelectField('Measure', default='par10',
        choices=[('mean', 'mean'), ('median', 'median'),
            ('par10', 'par10'), ('min', 'min'), ('max', 'max')])
    i = QuerySelectMultipleField('Instances', get_pk=lambda i: i.idInstance, allow_blank=True)
    instance_filter = TextField('Filter Instances')

class MonitorForm(Form):
    experiments = QuerySelectMultipleField('Experiments', get_label = lambda e: e.name)
    status = QuerySelectMultipleField('Status', get_label = lambda e: e.description)

class ClientForm(Form):
    experiments = QuerySelectMultipleField('Experiments', get_label = lambda e: e.name)