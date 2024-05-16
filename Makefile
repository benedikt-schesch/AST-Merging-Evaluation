all: style gradle-assemble

style: shell-script-style python-style java-style markdown-style

SH_SCRIPTS   = $(shell grep --exclude-dir=build --exclude-dir=repos --exclude-dir=cache -r -l '^\#! \?\(/bin/\|/usr/bin/env \)sh'   * | grep -v 'git-hires-merge' | grep -v /.git/ | grep -v '~$$' | grep -v '\.tar$$' | grep -v gradlew)
BASH_SCRIPTS = $(shell grep --exclude-dir=build --exclude-dir=repos --exclude-dir=cache -r -l '^\#! \?\(/bin/\|/usr/bin/env \)bash' * | grep -v /.git/ | grep -v '~$$' | grep -v '\.tar$$' | grep -v gradlew)
PYTHON_FILES = $(shell find .  -name '*.py' ! -path './repos/*' -not -path "./.workdir/*" -not -path "./cache*/*" | grep -v '/__pycache__/' | grep -v '/.git/' | grep -v gradlew)

CSV_RESULTS_COMBINED = results/combined/result.csv
CSV_RESULTS_GREATEST_HITS = results/greatest_hits/result.csv
CSV_RESULTS_REAPER = results/reaper/result.csv
CSV_RESULTS = $(CSV_RESULTS_COMBINED)

NUM_PROCESSES = 0

shell-script-style:
	shellcheck -e SC2153 -x -P SCRIPTDIR --format=gcc ${SH_SCRIPTS} ${BASH_SCRIPTS}
	checkbashisms ${SH_SCRIPTS}

showvars:
	@echo "SH_SCRIPTS=${SH_SCRIPTS}"
	@echo "BASH_SCRIPTS=${BASH_SCRIPTS}"
	@echo "PYTHON_FILES=${PYTHON_FILES}"

python-style:
	black ${PYTHON_FILES}
	pylint -f parseable --disable=W,invalid-name,c-extension-no-member,duplicate-code ${PYTHON_FILES}

check-python-style:
	black ${PYTHON_FILES} --check
	pylint -f parseable --disable=W,invalid-name --disable=W,duplicate-code ${PYTHON_FILES}

markdown-style:
	markdownlint "*.md" --disable MD013 --no-recursive

# This target deletes files that are not committed to version control.
clean:
	${MAKE} clean-workdir
	rm -rf repos
	rm -rf scratch
	rm -rf results/small
	rm -rf .valid_merges_counters

# This target deletes files in the cache, which is commited to version control.
clean-cache:
	rm -rf cache

# This target deletes files in the test cache.
clean-test-cache:
	rm -rf cache-small
	rm -f cache-small.tar

# This target deletes files that are committed to version control.
clean-stored-hashes:
	rm -f input_data/repos_small_with_hashes.csv
	rm -f input_data/repos_with_hashes.csv

# This target deletes files that are committed to version control.
clean-everything: clean clean-cache clean-test-cache clean-stored-hashes

# Compresses the cache.
compress-cache:
	if [ ! -d cache ]; then echo "cache does not exist"; exit 1; fi
	if [ -f cache.tar ]; then rm -f cache.tar; fi
	tar --exclude="lock" -czf cache.tar cache

compress-small-cache:
	if [ ! -d cache-small ]; then echo "cache-small does not exist"; exit 1; fi
	if [ -f cache-small.tar ]; then rm -f cache-small.tar; fi
	tar --exclude="lock" -czf cache-small.tar cache-small

# Decompresses the cache.
decompress-cache:
	if [ ! -f cache.tar ]; then echo "cache.tar does not exist"; exit 1; fi
	if [ -d cache ]; then echo "cache already exists"; exit 1; fi
	tar -xzf cache.tar

decompress-small-cache:
	if [ ! -f cache-small.tar ]; then echo "cache-small.tar does not exist"; exit 1; fi
	if [ -d cache-small ]; then echo "cache-small already exists"; exit 1; fi
	tar -xzf cache-small.tar

# Copy tables and plots to the paper.
copy-paper:
	rm -rf ../AST-Merging-Evaluation-Paper/results
	rsync -av --exclude='*.csv' results ../AST-Merging-Evaluation-Paper/
	find  ../AST-Merging-Evaluation-Paper/ -type d -empty -delete

# Update cache
update-cache-results:
	python3 src/python/cache_merger.py
	make compress-cache

# As of 2023-07-31, this takes 5-20 minutes to run, depending on your machine.
small-test:
	${MAKE} clean-test-cache clean
	./run_small.sh --include_trivial_merges --no_timing
	${MAKE} compress-small-cache
	${MAKE} small-test-diff
	rm -rf results/small
	./run_small.sh --include_trivial_merges --no_timing
	${MAKE} small-test-diff

small-test-without-cleaning:
	${MAKE} clean-test-cache
	./run_small.sh --include_trivial_merges --no_timing
	${MAKE} small-test-diff

update-figures:
	./run_combined.sh -op
	./run_greatest_hits.sh -op
	./run_reaper.sh -op

run-all:
	${MAKE} clean-workdir
	${MAKE} small-test-without-cleaning
	./run_combined.sh
	./run_greatest_hits.sh
	./run_reaper.sh


small-test-diff:
	python3 test/check_equal_csv.py --actual_folder results/small/ --goal_folder test/small-goal-files/
	@echo

gradle-assemble:
	./gradlew -q assemble -g ../.gradle/

clean-workdir:
	if [ -d .workdir ]; then chmod -R u+w .workdir; fi
	rm -rf .workdir

clean-local:
	${MAKE} clean-workdir
	rm -rf repos

check-merges-reproducibility:
	@echo "Running replay_merge for each idx in parallel using GNU Parallel..."
	@set -e; \
	tail -n +2 $(CSV_RESULTS) | awk -F, '{print $$1}' | parallel --halt now,fail=1 -j 50% python3 src/python/replay_merge.py --merges_csv $(CSV_RESULTS) -skip_build -delete_workdir --idx {}

protect-repos:
	find repos -mindepth 1 -type d -exec chmod a-w {} +

java-style:
	./gradlew -q spotlessCheck javadoc requireJavadoc -g ../.gradle/

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

run:
	nice -n 5 sh run_full.sh | tee output.txt

# Create a tarball of the artifacts for the paper.
# Keep this target last in the file.
create-artifacts:
	rm -rf artifacts
	git clone https://github.com/benedikt-schesch/AST-Merging-Evaluation.git artifacts
	rm -rf artifacts/.git
	sed -i '' 's/benedikt-schesch/anonymous-github-user/g' artifacts/README.md artifacts/Makefile
	tar -czf artifacts.tar.gz artifacts
