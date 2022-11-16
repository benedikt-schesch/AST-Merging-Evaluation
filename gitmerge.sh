# usage: ./gitmerge.sh <merge-dir> <output-dir>
leftdir=$1/left
basedir=$1/base
rightdir=$1/right
outputdir=$2

find $basedir -name "*.java" -or -name "**/*.java"|while read basename; do
    # construct paths
    suffix=${basename#"$basedir"}
    leftname=$leftdir$suffix
    rightname=$rightdir$suffix
    outputname=$outputdir$suffix

    # create output location
    mkdir -p $(dirname $outputname)
    touch $outputname

    # run git merge
    git merge-file -p $leftname $basename $rightname > $outputname
    
    # report conflicts
    retVal=$?
    if [ $retVal -ne 0 ]; then
        echo "Conflict"
        exit $retVal
    fi
done