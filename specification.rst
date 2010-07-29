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

Purpose
~~~~~~~~

The Web Competition System will assist researchers in hosting solver competitions
such as SAT Competition (http://www.satcompetition.org/) and provide a convenient
way to publish and access the setup, results and analysis of such a competition on
the web.

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
Solver
  Programs that runs on instances and provides solutions. Specifically: SAT solvers.
Solver Configuration
  A solver and a set of specified parameters and values that the solver should use.
Experiment
  An experiment consists of a set of solvers configurations, a set of instances, and a
  specified number of attempts for each solver on each instance.
  A competition will typically consist of several experiments based on categories
  such as Random, Application, ...

Overview
~~~~~~~~

The Web Competition Sytem will build on the existing EDACC infrastructure, i.e.
the Java Swing Application to create experiments, an (extended) EDACC database that
stores all data used by the system (such as solvers, instances, ...) and the
client, to run the experiments that are conducted in the competition on a computer
cluster.

A competition consists of several phases, which will be explained in detail in the
following sections.

The idea is to provide a web interface that can be used by competitors to send in
solvers and benchmarks and access the results of the experiments.

The organizers use the submitted solvers and benchmarks to create experiments and
run them on a cluster.

Description
-----------

General Information
~~~~~~~~~~~~~~~~~~~

The Web Competition System should be able to display certain static sites providing
general information about the competition, rules, time schedules, ...

Competition Phases
~~~~~~~~~~~~~~~~~~

The phases of a competition define the course of events in a competition and specify
the actions organizers and competitors have to take aswell as the information that
is visible in the web interface.

**1. Category definition phase:**

Organizers define competition categories such as "Random" or "Crafted".
The web interface will allow no competitor interaction in this phase, except
the access to general information, rules etc.

**2. Registration and Submission phase:**

In this phase competitors can register to the system and submit solvers and
benchmarks using the web interface.

*Registration:*
Competitors create an account which they have to use to log in to the web interface.
Account data includes the name, an email address, password and possibly additional
information such as an postal address and affiliation.

*Solver submission:*
Competitors submit their solvers to the system using the web interface.
They have to supply a name, version number, authors, a binary and the code.
Command line parameters of solvers can be specified aswell.
Additionally, a solver has to be assigned to one or more competition categories
as defined by the organizers in the previous phase.

*Benchmark submission:*
Every registered user can submit benchmarks that can be used by the organizers
in the competition or in the testing phase (see below).
A benchmark has to be categorized by the user in two ways:

- User source class: Used to specify the origin of a benchmark. A user can either
  define a new source class or choose one of the classes he created previously.
- Benchmark Type: Defined by the submitter. These types will probably correspond
  to the competition categories but can be further specified by the submitter.
  For example: "Application - CNF encoded MD5 attack"

**3. Solver Testing Phase:**

To ensure the submitted solvers are able to run on the competition cluster this
phase is used by the organizers to test the submitted solvers on a set of instances
that were submitted by the competitors or added by the organizers.

The Java application is used to create experiments corresponding to the competition
categories. The submitted solvers are assigned to experiments based on the category
assignment when they were submitted. The instances for each experiment are chosen
based on the benchmark type that was also specified on submission (or if they were
added by the organizers and are applicable).
These experiments are then run on the competition cluster.

During this phase competitors will only be able to see their own solver results and
benchmarks will only appear by name without further details.

**4. Solver Resubmission phase:**

During this phase competitors have the opportunity to resubmit solvers, if
bugs or compatibility issues with the cluster/system occured during the solver
testing phase. It is not possible to submit new solvers. Only solvers submitted
during the second phase can be updated with new versions.

It is up to the organizers how they want to handle updated versions. One possibility
is to rerun the experiments of the testing phase with the updated solvers and
let competitors access the same information as in the last phase.

**5. Competition phase:**

Similar to the testing phase, organizers create the competition experiments based
on the competition categories. Benchmark selection is a seperate issue and could be
managed by a jury prior to the experiment creation, for example.

The experiments are then run on the competition cluster. During this phase, competitors
have only access to their own solvers' results. Benchmarks appear by name only.

**6. Release phase:**

In this phase competitors gain access to the results of all competing solvers.
At this point a ranking has to be calculated and displayed using the results of
the solvers, for example number of instances solved correctly and breaking ties
by the accumulated time.
Solvers are ranked in each experiment separately and ranking calculations should
be done dynamically by the web competition system.

Also available in this phase should be analysis options such as various plots
visualizing the running times of solvers or certain properties of results and
instances. (Examples: Time vs. Memory, "Cactus-Plots", X vs. Y scatter plots, ...)

**7. Post-Relase phase:**

Benchmarks, results and possibly solver code and binaries are made publicly available
on the web interface.

Technical Details, Implementation
---------------------------------

The EDACC Web Competition System will be implemented in Python using various
widely used libraries and will be able to run on any web server that supports
the Python WSGI standard and has access to an EDACC database. To render analysis
plots the statistics language R will be used.