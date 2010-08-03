EDACC Web Competition System
============================
-------------
Specification
-------------

Introduction
------------

EDACC (Experiment Design and Administration for Computer Clusters) is a software
system consisting of a Java Swing application, a database and a client to manage and
run solvers for SAT and similar problems on computer clusters. This Web Competition
System aims to extend the existing functionality by providing a way to conduct
competitions and publish the results on the web.

See http://sourceforge.net/projects/edacc/ for the EDACC project.

Purpose
~~~~~~~~

The Web Competition System will assist researchers in hosting solver competitions
such as SAT Competition (http://www.satcompetition.org/) or simply compare their
own solvers and provide a convenient way to publish and access the setup, results
and analysis of such a competition or comparison on the web.

Abbreviations, Glossary
~~~~~~~~~~~~~~~~~~~~~~~

Some terms we will refer to in this document:

Admin : Organizer
  A person with administrative rights, typically part of the team hosting the
  competition.
User : Competitor
  A person competing with own solvers in the competition.
Instance : Benchmark
  A specific problem instance, e.g. a boolean formula.
Solver Configuration
  A solver and a set of specified parameters and their values which the solver should use.
Result
  The output or result of a solver that was run on a benchmark.
Experiment
  An experiment consists of a set of solvers configurations, a set of instances, and a
  specified number of attempts for each solver on each instance ("runs", interesting for
  solvers using random number generators).
  A competition will typically consist of several experiments based on categories
  such as Random, Application, ...

Overview
~~~~~~~~

The Web Competition Sytem will build on the existing EDACC infrastructure, i.e.
the Java Swing Application to create experiments, an (extended) EDACC database that
stores all data used by the system (such as solvers, instances, experiments, ...) and
the client, to run the experiments that are conducted in the competition on a computer
cluster.

A competition consists of several phases, which will be explained in detail in the
following sections.

The idea is to provide a web interface that can be used by competitors to send in
solvers and benchmarks and access the results of the experiments.

The organizers use the submitted solvers and benchmarks to create experiments and
run them on a cluster.

System Description
------------------

General Information
~~~~~~~~~~~~~~~~~~~

The Web Competition System should be able to display certain static websites
providing general information about the competition, rules, time schedules, ...
These static pages are written by the organizers.

Competition Phases
~~~~~~~~~~~~~~~~~~

The phases of a competition define the course of events in a competition and specify
the actions organizers and competitors have to take aswell as the information that
is visible in the web interface.

**1. Category definition phase:**

*1.1 Organizers:*
Define competition categories such as "Random" or "Crafted" in a database table.
This functionality can be offered through an admin section in the web interface.

*1.2 Competitors:*
The web interface will allow no competitor interaction in this phase, except for
the access to general information, rules, etc. on the static pages.

**2. Registration and Submission phase:**

*2.1 Organizers:*
Organizers are provided with an overview of the registered users and submitted solvers
and benchmarks. This could be done in the admin section of the web interface.

*2.2 Competitors:*
In this phase competitors can register with the system and submit solvers and
benchmarks using the web interface.

*Registration:*
Competitors create an account which they have to use to log in to the web interface.
Account data includes the name, an email address, password and possibly additional
information such as a postal address and affiliation.

*Solver submission:*
Competitors submit their solvers to the system using the web interface.
They have to provide a name, version number, authors, a binary and the code.
Command line parameters of solvers can be specified aswell. When creating the experiments,
organizers can then use the specified parameters to create the solver configurations.
Additionally, a solver has to be assigned to one or more competition categories
as defined by the organizers in the previous phase.

*Benchmark submission:*
Every registered user can submit benchmarks through the web interface that can be
used by the organizers in the competition or in the testing phase (see below).
A benchmark has to be categorized by the user in two ways:

- User source class: Used to specify the origin of a benchmark. A user can either
  define a new source class or choose one of the classes he created previously.
- Benchmark Type: Defined by the submitter. These types will probably correspond
  to the competition categories but can be further specified by the submitter.
  For example: "Application - CNF encoded MD5 attack"

During this phase competitors have no access to other competitors' solvers or
benchmarks.

**3. Solver Testing Phase:**

*3.1 Organizers:*
To ensure the submitted solvers are able to run on the competition cluster this
phase is used by the organizers to test the submitted solvers on a set of instances
that were submitted by the competitors or added by the organizers.

The Java application is used to create experiments corresponding to the competition
categories. The submitted solvers are assigned to experiments based on the category
assignment when they were submitted. The instances for each experiment are chosen
based on the benchmark type that was also specified on submission (or if they were
added by the organizers and are applicable).
These experiments are then run on the competition cluster.

*3.2 Competitors:*
During this phase competitors will only be able to see their own solver results and
benchmarks will only appear by name without further details in the web interface.
Registration and submission of solvers or benchmarks is no longer possible.

Visible information of each testing experiment:

- Live progress page showing the individual runs of a competitor's solvers as
  they are being executed.
- List of instances shown with their name only.
- List of all solvers the competitor submitted (more precisely the solver
  configurations created by the organizers with the parameters specified by the
  submitter)
- Results as specified in the "Results" section below but restricted to the competitors
  own solvers.

**4. Solver Resubmission phase:**

*4.1 Organizers:*
It is up to the organizers how they want to handle updated versions and feedback
to the competitors. One possibility is to rerun the experiments of the testing
phase with the updated solvers.

*4.2 Competitors:*
During this phase competitors have the opportunity to resubmit solvers, if
bugs or compatibility issues with the cluster/system occured during the solver
testing phase. It is not possible to submit new solvers. Only solvers submitted
during the second phase can be updated with new versions.

Competitors have access to the same information as in the last phase.

**5. Competition phase:**

*5.1 Organizers:*
Similar to the testing phase, organizers create the competition experiments based
on the competition categories. Benchmark selection is a seperate issue and could be
managed by a jury prior to experiment creation, for example.

The experiments are then run on the competition cluster.

*5.2 Competitors:*
During this phase, competitors have access to the same information as in the
testing phase, i.e. restricted to their own solvers' results.

**6. Release phase:**

In this phase competitors gain access to the results of all competing solvers.
At this point a ranking has to be calculated using the results of the solvers,
for example number of instances solved correctly and breaking ties by the accumulated time.
The ranking will be displayed by the web interface.
Ranking schemes have to be explored further as fair comparison of solvers is no trivial task.
The goal is to cleanly encapsulate the ranking calculation, so it's easy to change
the ranking scheme if needed.

Solvers are ranked in each experiment separately and ranking calculations should
be done, if possible, dynamically by the web competition system using the data
of the finished experiments.

Also available in this phase are analysis options including various plots
visualizing the running times of solvers or certain properties of results and
instances. (see "Analysis Options" below)

**7. Post-Release phase:**

Benchmarks, results and possibly solver code and binaries are made publicly available
on the web interface without requiring registration.

-------------------------------------


Results
~~~~~~~

Results are available in several views:

- *single result*: Output (stdout and stderr) and calculated result properties
  of one solver run on a benchmark. Additional technial information including
  the client's output.
- *by solver*: The results of one solver on all benchmarks of an experiment in a table
  with a column for each run, if a solver was run multiple times on each benchmark.
  Displayed information could include the runtime and other result properties.
- *by benchmark*: List of solvers and their results for a selected benchmark.
  Multiple runs can be represented in mulitple columns.
- *all solvers and benchmarks*: The results of all solvers on all benchmarks of
  an experiment in tabular format. One cell representing the runs of a solver (columns)
  on a benchmark (rows). Displayed information could include minimum, maximum,
  median and average run time if there were multiple runs.


Analyis Options
~~~~~~~~~~~~~~~

EDACC is currently being extended to allow the specification of properties of results
and instances, for example the "quality" or "simplicity" of a solution produced
by a solver or the number of variable flips needed.
These properties can be calculated for all results and instances before the release
phase by the organizers. They can then be used by the web competition system to
show various plots or allow statistical evaluation by calculating correlation coefficients etc.

Some examples:

- CPU time comparsion of 2 solvers in a scatter plot.
- Cactus plot of the number of instances solver given a certain amount of CPU time
  of all solvers in an experiment.
- CPU time vs. Memory scatter plot of one solver on the instances of an experiment.
- CPU time distributions of a solver on a benchmark if there were multiple runs

Additional features:

- exportable plots (as PDF, SVG, raw numbers, ...)
- Instance filtering for the relevant plots that contain more than one instance.
- "clickable" points in the plots leading e.g. to the instance they represent.


Technical Details, Implementation
---------------------------------

The EDACC Web Competition System will be implemented in Python utilizing various
widely used libraries and will be able to run on any web server that supports
the WSGI standard and has access to an EDACC database. To render plots it will
interface the statistical computing language R.

All user account data, submitted solvers and benchmarks will be stored in an EDACC
database. The static pages will have to be placed in a folder with a specified naming
scheme or alternatively, a third-party Wiki application could be utilized.

There are several places where caching will be useful to reduce page generation times,
for example result tables, plots and ranking. These can be held in caches, once
the experiments are finished.

Web Interface Structure
~~~~~~~~~~~~~~~~~~~~~~~

The following URL scheme roughly represents the structure of the web interface.
The root URL will allow the selection of one of the databases (=competitions) served
by the web interface.

::

    /                           (List of competitions/databases served)
    /<database>
        /Overview               (static)
        /Schedule               (static)
        /Rules                  (static)
        /Categories             (List of the experiments/categories of the competition)
        /<experiment>
            /Ranking            (in phases 6-7)
            /Progress           (3-6, live experiment progress information)
            /Results            (3-6)
                /By-Solver
                /By-Benchmark
                /...
            /Solvers            (3-6, List of solvers part of the current experiment)
            /Benchmarks         (3-6, ist of benchmarks)
            /Analysis           (5-6)
                /CPUTime
                /TimeVsMemory
                /...

        /Login                  (Login form)
        /Registration           (Registration form)
        /Manage                 (For competitors)
            /Solvers            (List of submitted solvers)
            /Benchmarks         (List of submitted benchmarks)
            /Submit-Solver      (Solver submission form)
            /Submit-Benchmark   (Benchmark submission form)
        /Admin                  (Admin section)