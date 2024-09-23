#!/bin/sh

# This checks that the implementations of various tools are consistent with one another.

set -e

SCRIPTDIR="$(cd "$(dirname "$0")" && pwd -P)"

# Check for identical content.

cd "$SCRIPTDIR"

diff -q ivn_plus.sh adjacent_plus.sh > /dev/null 2>&1 && { echo "identical: ivn_plus.sh adjacent_plus.sh"; exit 1; }
diff -q ivn_plus.sh gitmerge_ort_plus.sh
diff -q ivn_plus.sh imports_plus.sh
diff -q ivn_plus.sh version_numbers_plus.sh

diff -q ivn_ignorespace_plus.sh adjacent_ignorespace_plus.sh > /dev/null 2>&1 && { echo "identical: ivn_ignorespace_plus.sh adjacent_ignorespace_plus.sh"; exit 1; }
diff -q ivn_ignorespace_plus.sh gitmerge_ort_ignorespace_plus.sh
diff -q ivn_ignorespace_plus.sh imports_ignorespace_plus.sh
diff -q ivn_ignorespace_plus.sh version_numbers_ignorespace_plus.sh

# 


## These have an ignorespace version

tmpfile=$(mktemp)
tmpfile2=$(mktemp)

for base in adjacent imports ivn version_numbers ; do
    diff "$base.sh" "${base}_ignorespace.sh" > "$tmpfile" || true
    diff -q diff-pl-ignorespace.diff "$tmpfile" || { echo "problem with: diff $base.sh ${base}_ignorespace.sh, expected to be as in diff-pl-ignorespace.diff" ; exit 1; }
    diff "${base}_plus.sh" "${base}_ignorespace_plus.sh" > "$tmpfile" || true
    diff -q diff-pl-ignorespace.diff "$tmpfile" || { echo "problem with: diff ${base}_plus.sh ${base}_ignorespace_plus.sh, expected to be as in diff-pl-ignorespace.diff" ; exit 1; }

    diff "$base.sh" "${base}_plus.sh" > "$tmpfile" || true
    diff "${base}_ignorespace.sh" "${base}_ignorespace_plus.sh" > "$tmpfile2" || true
    diff -q "$tmpfile" "$tmpfile2" || { echo "problem with: ( $base.sh ${base}_plus .sh) versus ( ${base}_ignorespace.sh ${base}_ignorespace_plus.sh )"; exit 1; }
done


for base in gitmerge_ort gitmerge_recursive_myers ; do
    diff "$base.sh" "${base}_ignorespace.sh" > "$tmpfile" || true
    diff "${base}_plus.sh" "${base}_ignorespace_plus.sh" > "$tmpfile2" || true
    diff -q "$tmpfile" "$tmpfile2" || { echo "problem with: ( $base.sh ${base}_ignorespace.sh ) versus ( ${base}_plus.sh ${base}_ignorespace_plus.sh )"; exit 1; }


    diff "$base.sh" "${base}_plus.sh" > "$tmpfile" || true
    diff "${base}_ignorespace.sh" "${base}_ignorespace_plus.sh" > "$tmpfile2" || true
    diff -q "$tmpfile" "$tmpfile2" || { echo "problem with: ( $base.sh ${base}_plus.sh ) versus ( ${base}_ignorespace.sh ${base}_ignorespace_plus.sh )"; exit 1; }
done


## These do not have an ignorespace version

# "git_hires_merge.sh" has different diffs, so it is not included.
# TODO: Reinstate  gitmerge_resolve
for base in gitmerge_recursive_histogram gitmerge_recursive_minimal \
            gitmerge_recursive_patience ; do

    diff "$base.sh" "${base}_plus.sh" > "$tmpfile" || true
    diff -q diff-gm-plus.diff "$tmpfile" || { echo "problem with $base.sh ${base}_plus.sh, expected to be as in diff-gm-plus.diff"; exit 1; }

done

rm -rf "$tmpfile"
