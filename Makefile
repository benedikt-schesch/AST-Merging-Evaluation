all: style gradle-assemble

style: shell-script-style python-style java-style

SH_SCRIPTS   = $(shell grep --exclude-dir=build --exclude-dir=repos --exclude-dir=cache -r -l '^\#! \?\(/bin/\|/usr/bin/env \)sh'   * | grep -v /.git/ | grep -v '~$$' | grep -v '\.tar$$' | grep -v addrfilter | grep -v cronic-orig | grep -v gradlew | grep -v mail-stackoverflow.sh)
BASH_SCRIPTS = $(shell grep --exclude-dir=build --exclude-dir=repos --exclude-dir=cache -r -l '^\#! \?\(/bin/\|/usr/bin/env \)bash' * | grep -v /.git/ | grep -v '~$$' | grep -v '\.tar$$' | grep -v addrfilter | grep -v cronic-orig | grep -v gradlew | grep -v mail-stackoverflow.sh)

shell-script-style:
	shellcheck -e SC2153 -x -P SCRIPTDIR --format=gcc ${SH_SCRIPTS} ${BASH_SCRIPTS}
	checkbashisms ${SH_SCRIPTS}

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

# This target deletes files in the cache, which is commited to version control.
clean-cache:
	rm -rf cache

# This target deletes files in the test cache.
clean-test-cache:
	rm -rf test_cache

# This target deletes files that are committed to version control.
clean-stored-hashes:
	rm -f input_data/repos_small_with_hashes.csv
	rm -f input_data/repos_with_hashes.csv

# This target deletes files that are committed to version control.
clean-everything: clean clean-cache clean-test-cache clean-stored-hashes

# As of 2023-06-09, this takes 5-10 minutes to run, depending on your machine.
small-test:
	${MAKE} clean-test-cache clean
	./run_small.sh -d
	${MAKE} small-test-diff

small-test-diff:
# Print file names followed by file content.
	more results-small/*.csv results-small/merges/*.csv results-small/merges_valid/*.csv | cat
	if grep -Fqvf results-small/merges/ez-vcard.csv test/small-goal-files/merges/ez-vcard.csv; then exit 1; fi
	if grep -Fqvf results-small/merges/Algorithms.csv test/small-goal-files/merges/Algorithms.csv; then exit 1; fi
	(cd results-small && cat result.csv | rev | cut -d, -f10-65 | rev > result-without-times.csv)
	diff  -x merges -x .gitignore -x result.csv -x plots -x table_run_time.tex -x .DS_Store -r -U3 test/small-goal-files results-small
	rm -f test/small-goal-files/result-without-times.txt results-small/result-without-times.txt

gradle-assemble:
	./gradlew assemble -g ../.gradle/

java-style:
	./gradlew spotlessCheck javadoc requireJavadoc -g ../.gradle/

download-merge-tools: jars/IntelliMerge-1.0.9-all.jar jars/spork.jar

jars/IntelliMerge-1.0.9-all.jar:
	mkdir -p jars
	wget https://github.com/Symbolk/IntelliMerge/releases/download/1.0.9/IntelliMerge-1.0.9-all.jar -P jars/ --no-verbose

jars/spork.jar:
	mkdir -p jars
	wget https://github.com/KTH/spork/releases/download/v0.5.0/spork-0.5.0.jar -O jars/spork.jar --no-verbose

TAGS: tags
tags:
	etags ${SH_SCRIPTS} ${BASH_SCRIPTS} ${PYTHON_FILES}
