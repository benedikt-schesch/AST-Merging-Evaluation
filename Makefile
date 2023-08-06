all: style gradle-assemble

style: shell-script-style python-style java-style

SH_SCRIPTS   = $(shell grep --exclude-dir=build --exclude-dir=repos --exclude-dir=cache -r -l '^\#! \?\(/bin/\|/usr/bin/env \)sh'   * | grep -v 'git-hires-merge' | grep -v /.git/ | grep -v '~$$' | grep -v '\.tar$$' | grep -v gradlew)
BASH_SCRIPTS = $(shell grep --exclude-dir=build --exclude-dir=repos --exclude-dir=cache -r -l '^\#! \?\(/bin/\|/usr/bin/env \)bash' * | grep -v /.git/ | grep -v '~$$' | grep -v '\.tar$$' | grep -v gradlew)
# rwildcard = "recursive wildcard"
rwildcard=$(foreach d,$(wildcard $(1:=/*)),$(call rwildcard,$d,$2) $(filter $(subst *,%,$2),$d))
PYTHON_FILES=$(call rwildcard,.,*.py)

shell-script-style:
	shellcheck -e SC2153 -x -P SCRIPTDIR --format=gcc ${SH_SCRIPTS} ${BASH_SCRIPTS}
	checkbashisms ${SH_SCRIPTS}

showvars:
	@echo "SH_SCRIPTS=${SH_SCRIPTS}"
	@echo "BASH_SCRIPTS=${BASH_SCRIPTS}"
	@echo "PYTHON_FILES=${PYTHON_FILES}"

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

# Compresses the cache.
compress-cache:
	rm -r cache.tar
	tar --exclude="*explanation.txt" -czf cache.tar cache

# Decompresses the cache.
decompress-cache:
	if [ ! -f cache.tar ]; then echo "cache.tar does not exist"; exit 1; fi
	if [ -d cache ]; then echo "cache already exists"; exit 1; fi
	tar -xzf cache.tar

# Copy tables and plots to the paper.
copy-paper:
	rm -rf ../AST-Merging-Evaluation-Paper/tables ../AST-Merging-Evaluation-Paper/plots
	cp -r results/tables ../AST-Merging-Evaluation-Paper/tables
	cp -r results/plots ../AST-Merging-Evaluation-Paper/plots
	cp -r results/defs.tex ../AST-Merging-Evaluation-Paper/defs.tex
	find ../AST-Merging-Evaluation-Paper/tables -name '*.pdf' -delete
	find ../AST-Merging-Evaluation-Paper/plots -name '*.pdf' -delete

# Update cache
update-cache-results:
	python3 src/python/cache_merger.py
	make compress-cache

# As of 2023-07-31, this takes 5-20 minutes to run, depending on your machine.
small-test:
	${MAKE} clean-test-cache clean
	./run_small.sh -d
	${MAKE} small-test-diff

small-test-diff:
	@echo
	@echo "Here is the file content, in case a diff fails."
	more results-small/*.csv results-small/merges/*.csv results-small/merges_valid/*.csv | cat
	@echo
	if grep -Fqvf results-small/merges/ez-vcard.csv test/small-goal-files/merges/ez-vcard.csv; then exit 1; fi
	if grep -Fqvf results-small/merges/Algorithms.csv test/small-goal-files/merges/Algorithms.csv; then exit 1; fi
	test/remove-run_time-columns.py results-small/result.csv results-small/result-without-times.csv
	test/remove-run_time-columns.py results-small/filtered_result.csv results-small/filtered_result-without-times.csv
	@echo
	diff -x tools -x defs.tex -x git -x merges -x .gitignore -x git -x result.csv -x plots -x filtered_result.csv -x table_run_time.tex -x .DS_Store -x '*~' -x '#*#' -r -U3 test/small-goal-files results-small
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

# Create a tarball of the artifacts for the paper.
# Keep this target last in the file.
create-artifacts:
	rm -rf artifacts
	git clone https://github.com/benedikt-schesch/AST-Merging-Evaluation.git artifacts
	rm -rf artifacts/.git
	sed -i '' 's/benedikt-schesch/anonymous-github-user/g' artifacts/README.md artifacts/Makefile
	tar -czf artifacts.tar.gz artifacts
