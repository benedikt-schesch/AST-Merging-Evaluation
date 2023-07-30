#!/usr/bin/env bash

# usage: ./run_repo_tests.sh <repo-dir>

# This script runs the Maven or Gradle tests of a given repo.
# The exit status is 0 for test success or 1 for test failure.

set -o nounset

# Test side effects can be seen in the /tmp directory.
# We delete all the files older than 2h and owned by the current user.
find /tmp -maxdepth 1 -user "$(whoami)" -mmin +120 -exec rm -rf {} \;

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 REPO_DIR" >&2
  exit 1
fi
REPO_DIR=$1
cd "$REPO_DIR" || exit 1

if [ -f "gradlew" ] ; then
  command="./gradlew test -g ../.gradle/"
elif [ -f "mvnw" ] ; then
  mvn -version
  export MAVEN_OPTS="-Dmaven.repo.local=$REPO_DIR/.m2"
  command="./mvnw test"
elif [ -f pom.xml ] ; then
  mvn -version
  export MAVEN_OPTS="-Dmaven.repo.local=$REPO_DIR/.m2"
  command="mvn test"
else
  echo "No Gradle or Maven buildfile"
  exit 1
fi

if [ -z "${JAVA8_HOME:+isset}" ] ; then echo "JAVA8_HOME is not set"; exit 1; fi
if [ -z "${JAVA11_HOME:+isset}" ] ; then echo "JAVA11_HOME is not set"; exit 1; fi
if [ -z "${JAVA17_HOME:+isset}" ] ; then echo "JAVA17_HOME is not set"; exit 1; fi

# shellcheck disable=SC2153 # Not a typo of JAVA_HOME.
for javaX_home in $JAVA8_HOME $JAVA11_HOME $JAVA17_HOME
do
  if [ ! -d "${javaX_home}" ] ; then
    echo "No JDK ${javaX_home}"
    continue
  fi
  export JAVA_HOME=${javaX_home}
  export PATH="$JAVA_HOME/bin:$PATH"
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
