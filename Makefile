all: style gradle-assemble

style: shell-script-style python-style java-style

SH_SCRIPTS = 
BASH_SCRIPTS = $(shell find . -type d \( -path ./cache -o -path ./.workdir -o -path ./repos \) -prune -false -o -name '*.sh')

shell-script-style:
	shellcheck -e SC2153 -x -P SCRIPTDIR --format=gcc ${SH_SCRIPTS} ${BASH_SCRIPTS}
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

# This target deletes files that are not committed to version control.
clean:
	rm -rf .workdir
	rm -rf repos
	rm -rf scratch
	rm -rf results-small

# This target deletes files in the cache.
clean-cache:
	rm -rf cache

# This target deletes files that are committed to version control.
clean-stored-hashes:
	rm -f input_data/repos_small_with_hashes.csv
	rm -f input_data/repos_with_hashes.csv

# As of 2023-06-09, this takes 5-10 minutes to run, depending on your machine.
small-test:
	${MAKE} clean-cache clean
	./run_small.sh
	${MAKE} small-test-diff

small-test-diff:
# Print file names followed by file content.
	more results-small/*.csv results-small/merges/*.csv results-small/merges_valid/*.csv | cat
	if grep -Fqvf results-small/merges/ez-vcard.csv test/small-goal-files/merges/ez-vcard.csv; then exit 1; fi
	if grep -Fqvf results-small/merges/Algorithms.csv test/small-goal-files/merges/Algorithms.csv; then exit 1; fi
	(cd test/small-goal-files && cat result.csv | rev | cut -d, -f4-15 | rev > result-without-times.txt)
	(cd results-small && cat result.csv | rev | cut -d, -f4-15 | rev > result-without-times.txt)
	diff -r -U3 test/small-goal-files results-small -x merges -x .gitignore -x result.csv -x stacked.pdf -x table_runtime.txt -x .DS_Store
	rm -f test/small-goal-files/result-without-times.txt results-small/result-without-times.txt

gradle-assemble:
	./gradlew assemble -g ../.gradle/

java-style:
	./gradlew spotlessCheck javadoc requireJavadoc -g ../.gradle/

download-merge-tools: download-intellimerge download-spork

download-intellimerge:
	mkdir -p jars
	wget https://github.com/Symbolk/IntelliMerge/releases/download/1.0.9/IntelliMerge-1.0.9-all.jar -P jars/ --no-verbose

download-spork:
	mkdir -p jars
	wget https://github.com/KTH/spork/releases/download/v0.5.0/spork-0.5.0.jar -O jars/spork.jar --no-verbose

TAGS: tags
tags:
	etags ${SH_SCRIPTS} ${BASH_SCRIPTS} ${PYTHON_FILES}
