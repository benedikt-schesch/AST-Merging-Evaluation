# usage: ./spork.sh <merge-dir> <output-dir>
SPORK=./jars/spork.jar
leftdir=$1/left
basedir=$1/base
rightdir=$1/right
outputdir=$2

find $basedir -type f|while read basename; do
    # construct paths
    suffix=${basename#"$basedir"}
    leftname=$leftdir$suffix
    rightname=$rightdir$suffix
    outputname=$outputdir$suffix

    # create output location
    mkdir -p $(dirname $outputname)
    touch $outputname

    # run spork
    java -jar $SPORK -o=$outputname $leftname $basename $rightname

    # report conflicts
    retVal=$?
    if [ $retVal -ne 0 ]; then
        echo "Conflict"
        exit $retVal
    fi
done