# usage: ./gitmerge.sh <merge-dir> <output-dir>
leftdir=$1/left
basedir=$1/base
rightdir=$1/right
outputdir=$2

find $basedir -name "*.java" -or -name "**/*.java"|while read basename; do
    echo $basename
    suffix=${basename#"$basedir"}
    leftname=$leftdir$suffix
    rightname=$rightdir$suffix
    outputname=$outputdir$suffix
    git merge-file -p $leftname $basename $rightname > $outputname
done