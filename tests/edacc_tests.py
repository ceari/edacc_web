# -*- coding: utf-8 -*-
"""
    EDACC Web Frontend Tests
    ------------------------

    Unit tests of web frontend functions.

    :copyright: (c) 2010 by Daniel Diepold.
    :license: MIT, see LICENSE for details.
"""

import os
import unittest
import sys
import struct

# append parent directory to python path to be able to import edacc
sys.path.append("..")

class DatabaseConnectionTestCase(unittest.TestCase):
    def setUp(self):
        from edacc.web import app
        from edacc import models
        models.add_database("edacc", "edaccteam", "EDACCTest", "EDACCTest")
        self.db = models.get_database("EDACCTest")

    def test_db_connection(self):
        assert self.db is not None

    def test_competition_configuration(self):
        assert self.db.session.query(self.db.DBConfiguration).count() == 1
        assert self.db.session.query(self.db.DBConfiguration).get(0) is not None


class UtilsTestCase(unittest.TestCase):
    def setUp(self):
        from edacc import models
        models.add_database("edacc", "edaccteam", "EDACCTest", "EDACCTest")
        self.db = models.get_database("EDACCTest")
    
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
        from edacc import utils
        assert utils.formatOutputFile("") == ""
        assert utils.formatOutputFile(None) == "No output"
        assert utils.formatOutputFile("a" * 4096) == "a" * 4096
        assert utils.formatOutputFile("a" * 4097) == "a" * 2048 + "\n\n... [truncated 0 kB]\n\n" + "a" * 2048
    
    def test_newline_split_string(self):
        from edacc import utils
        assert utils.newline_split_string("test", 0) == "test"
        assert utils.newline_split_string("test", 4) == "test"
        assert utils.newline_split_string("test", 5) == "test"
        assert utils.newline_split_string("test", 1) == "t\ne\ns\nt"
        assert utils.newline_split_string("test", 2) == "te\nst"
        assert utils.newline_split_string("test", 3) == "tes\nt"
        
        
if __name__ == '__main__':
    unittest.main()