#!/usr/bin/env bash

# usage: ./run_repo_tests.sh <repo-dir>

# This script runs the Maven or Gradle tests of a given repo.
# The exit status is 0 for test success or 1 for test failure.

## TODO: Try different JVMs.

set -e
set -o nounset

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 REPO_DIR" >&2
  exit 1
fi

cd "$1"

if [ -f "gradlew" ] ; then
  command="./gradlew test --parallel"
elif [ -f "mvnw" ] ; then
  command="./mvnw test"
elif [ -f pom.xml ] ; then
  command="mvn test"
else
  echo "No Gradle or Maven buildfile"
  exit 1
fi

${command}
rc=$?
if $rc ; then
  echo "Test success: ${command}"
else
  echo "Test failure: ${command}"
fi

exit $rc
