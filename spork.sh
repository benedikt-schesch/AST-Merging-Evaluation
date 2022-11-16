# usage: ./spork.sh <merge-dir> <output-dir>
SPORK=./jars/spork.jar
leftdir=$1/left
basedir=$1/base
rightdir=$1/right
outputdir=$2

echo $basedir
for basename in $basedir/**/*; do
    echo $basename
    suffix=${fullname#"$basedir"}
    leftname=$leftdir$suffix
    rightname=$rightdir$suffix
    outputname=$outputdir$suffix
    echo $suffix
    java -jar $SPORK -o=$outputname $leftname $basename $rightname 
done