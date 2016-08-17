default:
test:
	# I do not know why nose cannot discover these itself,
	# so these paths are explicit.
	nosetests -v --with-doctest pb_git/cmds.py
	nosetests -v test/test_all.py
.PHONY: test
