# usage: ./spork.sh <merge-dir> <output-dir>
SPORK=./jars/spork.jar
leftdir=$1/left
basedir=$1/base
rightdir=$1/right
outputdir=$2

find $basedir -name "*.java" -or -name "**/*.java"|while read basename; do
    suffix=${basename#"$basedir"}
    leftname=$leftdir$suffix
    rightname=$rightdir$suffix
    outputname=$outputdir$suffix
    java -jar $SPORK -o=$outputname $leftname $basename $rightname
done