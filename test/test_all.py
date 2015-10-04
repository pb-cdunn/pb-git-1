from pb_git import (cmds, convert)
import nose.tools as nt
import StringIO
import sys

ver = sys.version[:3]

def test_capture():
    nt.assert_equal('hi', cmds.capture('echo hi').strip())

def test_system():
    nt.assert_equal(0, cmds.system('true'))
    nt.assert_equal(256, cmds.system('false', checked=False))

ini_content = """[general]
x = foo
y = 1

"""

def test_repo_config():
    ifs = StringIO.StringIO(ini_content)
    ofs = StringIO.StringIO()
    cfg = cmds.read_repo_config(ifs)
    cmds.write_repo_config(ofs, cfg)
    if ver > '2.6':
        # 2.7 uses OrderedDict
        nt.assert_equal(ini_content, ofs.getvalue())

git_submodules_content = """
    5d527739295c82bf4a141532d61019b9d155cc99 DALIGNER (heads/master)
    3e2231218d94f1f2a9083ae5695fb0d888b3e405 FALCON (0.2JASM-261-g3e22312)
    64d08e363e88b9356b587f2524fdc299a61d0791 pith (remotes/origin/HEAD)
"""

def test_map_sha1s():
    s = convert.map_sha1s(git_submodules_content)
    expected = {'FALCON': '3e2231218d94f1f2a9083ae5695fb0d888b3e405', 'DALIGNER': '5d527739295c82bf4a141532d61019b9d155cc99', 'pith': '64d08e363e88b9356b587f2524fdc299a61d0791'}
    nt.assert_equal(expected, s)
