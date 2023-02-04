#!/bin/bash

# usage: ./find_merge_commits.sh <repo-dir>

# This script take the path of a repo and tests it.
# It executes Maven or gradle depending on what is more suitable.

set -e 
set -o nounset

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 REPO_DIR" >&2
  exit 1
fi

cd $1
if [ -f "gradlew" ] ; then
  ./gradlew test
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

if [ -f "pom.xml" ] ; then
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
