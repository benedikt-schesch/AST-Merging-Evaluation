#!/usr/bin/env bash

# usage: ./run_repo_tests.sh <repo-dir>

# This script runs the Maven or Gradle tests of a given repo.
# The exit status is 0 for test success or 1 for test failure.

set -e
set -o nounset

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 REPO_DIR" >&2
  exit 1
fi

cd "$1"

if [ -f "gradlew" ] ; then
  command="./gradlew test -g ../.gradle/"
elif [ -f "mvnw" ] ; then
  command="./mvnw test"
elif [ -f pom.xml ] ; then
  command="mvn test"
else
  echo "No Gradle or Maven buildfile"
  exit 1
fi

for i in $JAVA_8 $JAVA_11 $JAVA_17
do
  if [ ! -d "$i" ] ; then
    echo "No JDK $i"
    continue
  fi
  export JAVA_HOME=$i
  export PATH="$JAVA_HOME:$PATH"
  echo "Running tests with JAVA_HOME=$JAVA_HOME"
  ${command}
  rc=$?
  if [ $rc -eq 0 ] ; then
    echo "Test success: ${command}"
    exit $rc
  else
    echo "Test failure: ${command}"
  fi
done
echo 
exit 1