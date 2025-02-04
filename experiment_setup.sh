rm -rf .workdir/Merge-Examples
cp -r .workdir/Merge-Examples2 .workdir/Merge-Examples

./src/scripts/merge_tools/deepseek70b_merge.sh .workdir/Merge-Examples left right "-s ort"
# ./src/scripts/merge_tools/ollama_merge.sh .workdir/Merge-Examples left right "-s ort" deepseek-r1:70b
