# -*- coding: utf-8 -*-
"""
    EDACC Web Frontend Tests
    ------------------------

    Unit tests of web frontend functions.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import unittest
import sys
import struct

from sqlalchemy import func

import fixtures

# append parent directory to python path to be able to import edacc
sys.path.append("..")

TEST_DATABASE = "EDACCUnitTests"

def clean_database(db):
    db.session.query(db.ExperimentResult).delete()
    db.session.query(db.Experiment).delete()
    db.session.query(db.Instance).delete()
    db.session.query(db.Solver).delete()
    db.session.query(db.InstanceClass).delete()
    db.session.commit()

def float_eq(x, y, eps=1e-10):
    return y - eps <= x <= y + eps

class DatabaseConnectionTestCase(unittest.TestCase):
    def setUp(self):
        from edacc.web import app
        from edacc import models
        self.db = models.add_database("edacc", "edaccteam", TEST_DATABASE, TEST_DATABASE)

    def test_db_connection(self):
        assert self.db is not None

    def test_competition_configuration(self):
        assert self.db.session.query(self.db.DBConfiguration).count() == 1
        assert self.db.session.query(self.db.DBConfiguration).get(0) is not None

class RankingTestCase(unittest.TestCase):
    def setUp(self):
        from edacc import models
        self.db = db = models.add_database("edacc", "edaccteam", TEST_DATABASE, TEST_DATABASE)
        clean_database(db)
        fixtures.setup_ranking_fixture(db)

    def test_fixture(self):
        db = self.db
        assert db.session.query(db.Experiment).count() == 1
        assert db.session.query(db.ExperimentResult).count() == 10*10*10

    def test_number_of_solved_instances_ranking(self):
        from edacc import ranking
        db = self.db
        experiment = db.session.query(db.Experiment).first()
        instances = experiment.instances
        ranked_solver_configs = ranking.number_of_solved_instances_ranking(db, experiment, instances)
        assert len(ranked_solver_configs) == 10
        assert ranked_solver_configs[0].name == u"TestSolver0Configuration"
        assert ranked_solver_configs[9].name == u"TestSolver9Configuration"
        ranking_data = ranking.get_ranking_data(db, experiment, ranked_solver_configs, instances, True, True)
        assert ranking_data[0][0] == u"Virtual Best Solver (VBS)"
        assert ranking_data[0][1] == 10*10 # 10 instances, 10 runs each
        assert ranking_data[0][2] == 1.0
        assert ranking_data[0][4] == 10*10*1.0 # 10 instances, 10 runs each, best time should be 1.0 on each

        best = ranking_data[1]
        assert best[0].name == u"TestSolver0Configuration"
        assert best[1] == 10*10
        assert best[2] == 1.0
        assert best[3] == 1.0
        assert best[4] == 10*10*1.0 # 10 instances, 10 runs each, best time should be 1.0 on each
        assert best[5] == 1.0 # avg cpu time per run
        assert best[6] == 0.0 # avg stddev per instance
        assert best[7] == 1.0 # par10

        second = ranking_data[2]
        assert second[0].name == u"TestSolver1Configuration"
        assert second[1] == 10*10
        assert second[2] == 1.0
        assert second[3] == 1.0
        assert second[4] == 10*10*2.0
        assert second[5] == 2.0
        assert second[6] == 0.0
        assert second[7] == 2.0

    def tearDown(self):
        clean_database(self.db)
        self.db.session.remove()

class StatisticsTestCase(unittest.TestCase):
    def test_probabilistic_domination(self):
        from edacc.statistics import prob_domination

        v1 = [1, 2, 3, 4, 5]
        v2 = [1, 2, 3, 4, 5]
        assert prob_domination(v1, v2) == 0
        assert prob_domination(v2, v1) == 0
        assert prob_domination(v1, v1) == 0

        v1 = [1, 2, 3, 4, 4.5]
        v2 = [1, 2, 3, 4, 5]
        assert prob_domination(v1, v2) == 1
        assert prob_domination(v2, v1) == -1

        v1 = [1, 2, 3]
        v2 = [1, 2, 2, 1, 1, 1.5]
        assert prob_domination(v1, v2) == -1
        assert prob_domination(v2, v1) == 1

        v1 = [1, 1, 1, 1]
        v2 = [1, 1, 1, 1, 1, 1, 5]
        assert prob_domination(v1, v2) == 1
        assert prob_domination(v2, v1) == -1

    def test_spearman_correlation(self):
        from edacc.statistics import spearman_correlation
        rho, p = spearman_correlation([1.0, 2.0, 3.0, 4.0], [2.0, 3.0, 4.0, 5.0])
        assert rho == 1.0

    def test_pearson_correlation(self):
        from edacc.statistics import pearson_correlation
        rho, p = pearson_correlation([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0])
        assert rho == 1.0 and p <= 1e-10

    def test_kolmogorow_smirnow_2sample_test(self):
        from edacc.statistics import kolmogorow_smirnow_2sample_test
        D, p = kolmogorow_smirnow_2sample_test([1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0])
        assert float_eq(D, 1.0) and float_eq(p, 0.02857, eps=1e-5)
        D, p = kolmogorow_smirnow_2sample_test([1.0, 2.0, 3.0, 4.0, 10.0], [5.0, 6.0, 7.0, 8.0])
        assert float_eq(D, 0.8) and float_eq(p, 0.07937, eps=1e-5)

    def test_wilcox_test(self):
        from edacc.statistics import wilcox_test
        W, p = wilcox_test([1.0, 2.0, 3.0, 3.5, 3.8], [5.0, 6.0, 7.0, 8.0])
        assert W == 0 and float_eq(p, 0.01587, eps=1e-5)
        W, p = wilcox_test([1.0, 2.0, 3.0, 4.0, 10.0], [5.0, 6.0, 7.0, 8.0])
        assert W == 4  and float_eq(p, 0.1905, eps=1e-4)

class UtilsTestCase(unittest.TestCase):
    def test_lzma_compression(self):
        from edacc import utils
        uncompressed_data = "TestData with \x12\x65 weird bytes \n and everything"
        compressed_data = utils.lzma_compress(uncompressed_data)
        decompressed_data = utils.lzma_decompress(compressed_data)
        assert decompressed_data == uncompressed_data
        assert len(compressed_data) > 13 # there should always be a 13 bytes header
        len_bytes = struct.unpack('<Q', compressed_data[5:13])[0]
        assert len_bytes == len(uncompressed_data)

    def test_format_output_file(self):
        from edacc.utils import formatOutputFile
        assert formatOutputFile("") == ""
        assert formatOutputFile(None) == "No output"
        assert formatOutputFile("a" * 4096) == "a" * 4096
        assert formatOutputFile("a" * 4097) == "a" * 2048 + "\n\n... [truncated 0 kB]\n\n" + "a" * 2048

    def test_newline_split_string(self):
        from edacc.utils import newline_split_string
        assert newline_split_string("test", 0) == "test"
        assert newline_split_string("test", 4) == "test"
        assert newline_split_string("test", 5) == "test"
        assert newline_split_string("test", 1) == "t\ne\ns\nt"
        assert newline_split_string("test", 2) == "te\nst"
        assert newline_split_string("test", 3) == "tes\nt"

    def test_download_size(self):
        from edacc.utils import download_size
        assert download_size(0) == "0 Bytes"
        assert download_size(1) == "1 Bytes"
        assert download_size(1024) == "1.0 kB"
        assert download_size(1024*1024) == "1.0 MB"

    def test_parse_parameters(self):
        from edacc.utils import parse_parameters
        params = parse_parameters("-p1 5 -p2 -p3 4.0 -p5 abc -p6 2.0")
        assert ("-p1", "-p1", "5", False, 0) in params
        assert ("-p2", "-p2", "", True, 2) in params
        assert ("-p3", "-p3", "4.0", False, 3) in params
        assert ("-p5", "-p5", "abc", False, 5) in params
        assert ("-p6", "-p6", "2.0", False, 7) in params

        params = parse_parameters("-p1 1.0 -i INSTANCE SEED")
        assert ("-p1", "-p1", "1.0", False, 0) in params
        assert ("instance", "-i", "", False, 2) in params
        assert ("seed", "", "", False, 4) in params

class AnalysisTestCase(unittest.TestCase):
    def setUp(self):
        from edacc import models, config
        config.DEFAULT_DATABASES = [("edacc", "edaccteam", TEST_DATABASE, TEST_DATABASE, True)]
        from edacc.web import app
        self.app = app.test_client()
        self.db = db = models.add_database("edacc", "edaccteam", TEST_DATABASE, TEST_DATABASE)
        clean_database(db)
        fixtures.setup_ranking_fixture(db)

    def test_solver_ranking(self):
        exp = self.db.session.query(self.db.Experiment).first()
        assert "The virtual best solver" in self.app.get('/'+TEST_DATABASE+"/experiment/" + \
                str(exp.idExperiment) + "/ranking/").data

    def tearDown(self):
        clean_database(self.db)
        self.db.session.remove()



if __name__ == '__main__':
    unittest.main()
