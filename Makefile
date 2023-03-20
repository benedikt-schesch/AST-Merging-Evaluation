style: shell-script-style python-style

SH_SCRIPTS = 
BASH_SCRIPTS = $(shell find . -name '*.sh' -not -path "./repos/*" -not -path "./.workdir/*")

shell-script-style:
	shellcheck -x -P SCRIPTDIR --format=gcc ${SH_SCRIPTS} ${BASH_SCRIPTS}
#	checkbashisms ${SH_SCRIPTS}

showvars:
	@echo "SH_SCRIPTS=${SH_SCRIPTS}"
	@echo "BASH_SCRIPTS=${BASH_SCRIPTS}"

PYTHON_FILES=$(wildcard src/python/*.py)
python-style:
	black ${PYTHON_FILES}
	pylint -f parseable --disable=W,invalid-name --disable=W,duplicate-code ${PYTHON_FILES}

check-python-style:
	black ${PYTHON_FILES} --check
	pylint -f parseable --disable=W,invalid-name --disable=W,duplicate-code ${PYTHON_FILES}

clean:
	rm -f small/valid_repos.csv

clean-cache:
	rm -rf cache
	rm -rf .workdir
	rm -rf repos
	rm -rf scratch

# This target deletes files that are committed to version control.
clean-stored-hashes:
	rm -f data/repos_small_with_hashes.csv
	rm -f data/repos_with_hashes.csv

small-test:
	run_small.sh
	${MAKE} diff-small-test

small-test-diff:
	diff -U3 -r small test/small-goal-files
