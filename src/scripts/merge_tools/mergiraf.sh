#!/usr/bin/env bash

# usage: <scriptname> [--verbose] <clone_dir> <branch-1> <branch-2>
# <clone_dir> must contain a clone of a repository.
# Merges branch2 into branch1, in <clone_dir>.
# Return code is 0 for merge success, 1 for merge failure, 2 for script failure.
# For merge failure, also outputs "Conflict" and aborts the merge.

set -o nounset

verbose=
if [ "$1" = "--verbose" ] ; then
  # shellcheck disable=SC2034 # unused
  verbose="$1"
  shift
fi

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 [--verbose] CLONE_DIR BRANCH1 BRANCH2" >&2
  exit 2
fi

MERGIRAF_VERSION="0.3.0"

SCRIPT_PATH="$(dirname "$0")"; SCRIPT_PATH="$(eval "cd \"$SCRIPT_PATH\" && pwd")"
ROOT_PATH="$(realpath "${SCRIPT_PATH}/../../../")"
mergiraf_relativepath=bin/mergiraf
mergiraf_absolutepath="${ROOT_PATH}/${mergiraf_relativepath}"
mkdir -p ${ROOT_PATH}/bin

if [ ! -e $mergiraf_absolutepath ]; then
  ARCH=$(uname -m)
  if [[ "$ARCH" == x86_64* ]]; then
    ARCH="x86_64"
  elif [[ "$ARCH" == i*86 ]]; then
    echo "No mergiraf binaries for architecture $ARCH"
    exit 2
  elif  [[ "$ARCH" == arm* ]]; then
    ARCH="aarch64"
  fi
  if [[ $OSTYPE == 'darwin'* ]]; then
    VENDOR="apple-darwin"
  else
    VENDOR="unknown-linux-gnu"
  fi
  FULL_ARCH="${ARCH}-${VENDOR}"

  wget https://codeberg.org/mergiraf/mergiraf/releases/download/v${MERGIRAF_VERSION}/mergiraf_${FULL_ARCH}.tar.gz -O ${ROOT_PATH}/bin/mergiraf.tar.gz
  tar -zxf ${ROOT_PATH}/bin/mergiraf.tar.gz -C ${ROOT_PATH}/bin/
  rm ${ROOT_PATH}/bin/mergiraf.tar.gz
fi

clone_dir=$1
branch1=$2
branch2=$3

cd "$clone_dir" || { echo "$0: cannot cd to $clone_dir"; exit 2; }

# set up mergiraf driver
git config --global merge.mergiraf.name mergiraf
git config --global merge.mergiraf.driver "${mergiraf_absolutepath} merge --git %O %A %B -s %S -x %X -y %Y -p %P"
$(mergiraf_absolutepath) languages --gitattributes >> .gitattributes

# perform merge
git checkout "$branch1" --force
git merge --no-edit "$branch2"
retVal=$?

# report conflicts
if [ $retVal -ne 0 ]; then
    echo "mergiraf.sh: Conflict"
fi

exit $retVal
