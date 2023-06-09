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
	rm -rf small/

# This target deletes files that are committed to version control.
clean-cache:
	rm -rf cache
	rm -rf .workdir
	rm -rf repos
	rm -rf scratch

# This target deletes files that are committed to version control.
clean-stored-hashes:
	rm -f data/repos_small_with_hashes.csv
	rm -f data/repos_with_hashes.csv

# As of 2023-06-09, this takes 5-10 minutes to run, depending on your machine.
small-test:
	${MAKE} clean-cache
	./run_small.sh
	${MAKE} small-test-diff

small-test-diff:
	cat small/local_repos.csv
	cat small/merges/Algorithms.csv
	cat small/merges/ez-vcard.csv
	cat small/merges_valid/Algorithms.csv
	cat small/merges_valid/ez-vcard.csv
	cat small/result.csv
	if grep -Fqvf small/merges/ez-vcard.csv test/small-goal-files/merges/ez-vcard.csv; then exit 1; fi
	if grep -Fqvf small/merges/Algorithms.csv test/small-goal-files/merges/Algorithms.csv; then exit 1; fi
	(cd test/small-goal-files && cat result.csv | rev | cut -d, -f4-15 | rev > result-without-times.txt)
	(cd small && cat result.csv | rev | cut -d, -f4-15 | rev > result-without-times.txt)
	diff -r -U3 test/small-goal-files small -x merges -x .gitignore -x result.csv -x stacked.pdf -x table_runtime.txt -x .DS_Store
	rm -f test/small-goal-files/result-without-times.txt small/result-without-times.txt
