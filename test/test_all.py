from nose.tools import *
import pb_git.run as run
import StringIO
import sys

ver = sys.version[:3]

def test_capture():
    assert_equal('hi', run.capture('echo hi').strip())
def test_system():
    assert_equal(0, run.system('true'))
    assert_equal(256, run.system('false', checked=False))

ini_content = """[general]
x = foo
y = 1

"""

def test_repo_config():
    ifs = StringIO.StringIO(ini_content)
    ofs = StringIO.StringIO()
    cfg = run.read_repo_config(ifs)
    run.write_repo_config(ofs, cfg)
    if ver > '2.6':
        # 2.7 uses OrderedDict
        assert_equal(ini_content, ofs.getvalue())
