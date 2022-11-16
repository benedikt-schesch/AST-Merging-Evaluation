# usage: ./intellmerge.sh <repo> <branch1> <branch2> <outputdir>
INTELLIMERGE=./jars/IntelliMerge-1.0.9-all.jar
repo=$1
branch1=$2
branch2=$3
outputdir=$4

# run intellimerge
java -jar $INTELLIMERGE -r $repo -b $branch1 $branch2 -o $outputdir

# report conflicts
grep -rq -m 1 "<<<<<<<" $outputdir
retVal=$?
if [ $retVal -eq 0 ]; then
    echo "Conflict"
    exit 1
fi
exit 0