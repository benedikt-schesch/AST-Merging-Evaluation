rm -rf .workdir-test/Algorithms
cp -r .workdir-test/Algorithms2 .workdir-test/Algorithms

./src/scripts/merge_tools/deepseekr1_merge_plus.sh .workdir-test/Algorithms left right "-s ort"
# ./src/scripts/merge_tools/ollama_merge.sh .workdir/Merge-Examples left right "-s ort" deepseek-r1:70b
