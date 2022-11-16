# usage: ./intellmerge.sh <merge-dir> <output-dir>
INTELLIMERGE=./jars/IntelliMerge-1.0.9-all.jar
leftdir=$1/left
basedir=$1/base
rightdir=$1/right
outputdir=$2

java -jar $INTELLIMERGE -d $leftdir $basedir $rightdir -o $outputdir

currentdir=$(pwd)
mkdir temp
mv output/$currentdir/* temp
rm -r output/*/
mv temp/* output
rmdir temp