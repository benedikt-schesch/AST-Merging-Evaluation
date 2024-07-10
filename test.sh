#!/bin/bash

rm -rf replay_output .workdir run_small_output
python3 src/python/utils/delete_intellimerge_keys_from_cache.py --cache cache-small/sha_cache_entry/mangstadt --yes
./run_small.sh --include_trivial_merges --no_timing
cp -r .workdir/mangstadt/ez-vcard/merge-tester-intellimerge-ea6026ee62cc184db68d841d50d58474fcdf4862-ab2032ca9769d452d4906f51cf56ca7d983a27c4 run_small_output
python3 src/python/replay_merge.py --merges_csv results/small/result.csv --idx 1-7
cp -r .workdir/mangstadt/ez-vcard-merge-replay-intellimerge-ea6026ee62cc184db68d841d50d58474fcdf4862-ab2032ca9769d452d4906f51cf56ca7d983a27c4 replay_output
rm -rf .workdir
