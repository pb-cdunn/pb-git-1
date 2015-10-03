from nose.tools import *

class TestFoo(object):
    def test_pass(self):
        assert_equal(1, 1)
    def test_fail(self):
        assert_equal(1, 2)
