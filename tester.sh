#!/bin/bash

cd $1
if [ -f "gradlew" ]
then

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

else
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
