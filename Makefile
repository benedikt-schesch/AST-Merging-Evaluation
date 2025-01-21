all: check-style gradle-assemble

fix-style: fix-python-style fix-java-style

check-style: check-shell-script-style check-python-style check-java-style

SH_SCRIPTS   = $(shell grep --exclude-dir=build --exclude-dir=repos --exclude-dir=cache -r -l '^\#! \?\(/bin/\|/usr/bin/env \)sh'   * | grep -v 'git-hires-merge' | grep -v /.git/ | grep -v '~$$' | grep -v '\.tar$$' | grep -v gradlew)
BASH_SCRIPTS = $(shell grep --exclude-dir=build --exclude-dir=repos --exclude-dir=cache -r -l '^\#! \?\(/bin/\|/usr/bin/env \)bash' * | grep -v /.git/ | grep -v '~$$' | grep -v '\.tar$$' | grep -v gradlew)
PYTHON_FILES = $(shell find .  -name '*.py' ! -path './repos/*' -not -path "./.workdir/*" -not -path "./cache*/*" | grep -v '/__pycache__/' | grep -v '/.git/' | grep -v gradlew | grep -v git-hires-merge)

CSV_RESULTS_COMBINED = results/combined/result_raw.csv
CSV_RESULTS_GREATEST_HITS = results/greatest_hits/result_raw.csv
CSV_RESULTS_REAPER = results/reaper/result_raw.csv
CSV_RESULTS = $(CSV_RESULTS_COMBINED)

showvars:
	@echo "SH_SCRIPTS=${SH_SCRIPTS}"
	@echo "BASH_SCRIPTS=${BASH_SCRIPTS}"
	@echo "PYTHON_FILES=${PYTHON_FILES}"

check-shell-script-style:
	shellcheck -e SC2153 -x -P SCRIPTDIR --format=gcc ${SH_SCRIPTS} ${BASH_SCRIPTS}
	checkbashisms ${SH_SCRIPTS}

fix-python-style:
	ruff format ${PYTHON_FILES}
	ruff check ${PYTHON_FILES} --fix

check-python-style:
	ruff format ${PYTHON_FILES} --check
	ruff check ${PYTHON_FILES}

fix-java-style:
	./gradlew -q spotlessApply -g ../.gradle/

check-java-style:
	./gradlew -q spotlessCheck javadoc requireJavadoc -g ../.gradle/

# This target deletes files that are not committed to version control.
clean:
	${MAKE} clean-workdir
	rm -rf repos-small-test
	rm -rf scratch
	rm -rf results/small
	rm -rf .valid_merges_counters

clean-repos:
	rm -rf repos
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
	if [ ! -d cache ]; then echo "cache does not exist"; exit 2; fi
	if [ -f cache.tar.gz ]; then rm -f cache.tar.gz; fi
	tar --exclude="lock" -czf cache.tar.gz cache

# Compresses the cache without logs.
compress-cache-without-logs:
	if [ ! -d cache ]; then echo "cache does not exist"; exit 2; fi
	if [ -f cache_without_logs.tar.gz ]; then rm -f cache_without_logs.tar.gz; fi
	tar --exclude="lock" --exclude="logs" -czf cache_without_logs.tar.gz cache

compress-small-cache:
	if [ ! -d cache-small ]; then echo "cache-small does not exist"; exit 2; fi
	if [ -f cache-small.tar ]; then rm -f cache-small.tar; fi
	tar --exclude="lock" -czf cache-small.tar cache-small

# Decompresses the cache.
decompress-cache:
	if [ ! -f cache.tar.gz ]; then echo "cache.tar.gz does not exist"; exit 2; fi
	if [ -d cache ]; then echo "cache already exists"; exit 2; fi
	tar -xzf cache.tar.gz

# Decompresses the cache without logs.
decompress-cache-without-logs:
	if [ ! -f cache_without_logs.tar.gz ]; then echo "cache_without_logs.tar.gz does not exist"; exit 2; fi
	if [ -d cache ]; then echo "cache already exists"; exit 2; fi
	tar -xzf cache_without_logs.tar.gz

decompress-small-cache:
	if [ ! -f cache-small.tar ]; then echo "cache-small.tar does not exist"; exit 2; fi
	if [ -d cache-small ]; then echo "cache-small already exists"; exit 2; fi
	tar -xzf cache-small.tar

# Copy tables and plots to the paper.
copy-paper:
	rm -rf ../AST-Merging-Evaluation-Paper/results
	rsync -av --exclude='*.csv' results ../AST-Merging-Evaluation-Paper/
	find  ../AST-Merging-Evaluation-Paper/ -type d -empty -delete

# As of 2023-07-31, this takes 5-20 minutes to run, depending on your machine.
small-test:
	${MAKE} clean-test-cache clean
	AST_REPOS_PATH=repos-small-test DELETE_WORKDIRS=False WORKDIR_DIRECTORY=.workdir-small-test ./run_small.sh --include_trivial_merges --no_timing
	python3 test/check_hashes.py
	${MAKE} compress-small-cache
	${MAKE} small-test-diff
	rm -rf results/small
	AST_REPOS_PATH=repos-small-test DELETE_WORKDIRS=False WORKDIR_DIRECTORY=.workdir-small-test ./run_small.sh --include_trivial_merges --no_timing
	${MAKE} small-test-diff

small-test-without-cleaning:
	${MAKE} clean-test-cache
	AST_REPOS_PATH=repos-small-test DELETE_WORKDIRS=False WORKDIR_DIRECTORY=.workdir-small-test ./run_small.sh --include_trivial_merges --no_timing
	python3 test/check_hashes.py
	${MAKE} small-test-diff

update-figures:
	./run_combined.sh -op
	./run_greatest_hits.sh -op --no_timing
	./run_reaper.sh -op --no_timing

update-figures-small:
	AST_REPOS_PATH=repos-small-test DELETE_WORKDIRS=False WORKDIR_DIRECTORY=.workdir-small-test ./run_small.sh -op --no_timing

update-small-results:
	rm -rf test/small-goal-files/
	rsync -av --exclude='*.pdf' --exclude='*.png' --exclude='*unhandled_and_failed_merges_without_intellimerge*' --exclude='*.pgf' results/small/ test/small-goal-files/

run-all-without-timing:
	${MAKE} clean-workdir
	${MAKE} small-test-without-cleaning
	./run_combined.sh --no_timing
	./run_greatest_hits.sh --no_timing
	./run_reaper.sh --no_timing

run-all:
	${MAKE} clean-workdir
	${MAKE} small-test-without-cleaning
	./run_combined.sh
	./run_greatest_hits.sh --no_timing
	./run_reaper.sh --no_timing

run-all-without-small-test:
	./run_combined.sh
	./run_greatest_hits.sh --no_timing
	./run_reaper.sh --no_timing

small-test-diff:
	python3 test/check_equal_csv.py --actual_folder results/small/ --goal_folder test/small-goal-files/
	@echo

gradle-assemble:
	./gradlew -q assemble -g ../.gradle/

clean-workdir:
	if [ -d .workdir ]; then chmod -R u+w .workdir; fi
	rm -rf .workdir
	if [ -d .workdir-small-test ]; then chmod -R u+w .workdir-small-test; fi
	rm -rf .workdir-small-test

clean-local:
	${MAKE} clean-workdir
	rm -rf repos-small-test

check-merges-reproducibility:
	@echo "Running replay_merge sequentially for each idx..."
	@set -e; \
	FAILED_IDXES=""; \
	for idx in $(shell tail -n +2 $(CSV_RESULTS) | awk -F, '{print $$1}'); do \
		echo "Running replay_merge for idx $$idx"; \
		src/python/replay_merge.py --testing --merges_csv $(CSV_RESULTS) -skip_build -delete_workdir --idx $$idx || FAILED_IDXES="$$FAILED_IDXES $$idx"; \
	done; \
	test -z "$$FAILED_IDXES" || { echo "Failed indexes = $$FAILED_IDXES"; false; }

protect-repos:
	find repos -mindepth 1 -type d -exec chmod a-w {} +

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
	nice -n 5 sh run_combined.sh | tee output.txt
