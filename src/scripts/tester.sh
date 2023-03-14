#!/bin/bash

# usage: ./tester.sh <repo-dir>

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
  ./gradlew test --parallel
  rc=$?
  if [ $rc -ne 0 ] ; then
    echo Gradle Test Failure
    exit 1
  fi
  if [ $rc -eq 0 ] ; then
    echo Gradle Test Success
    exit 0
  fi
fi

if [[ -f pom.xml || -f mvnw ]] ; then
  mvn test
  rc=$?
  if [ $rc -ne 0 ] ; then
    echo Maven Test Failure
    exit 1
  fi
  if [ $rc -eq 0 ] ; then
    echo Maven Test Success
    exit 0
  fi
fi

exit 1
