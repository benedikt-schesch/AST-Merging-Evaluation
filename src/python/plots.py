#!/usr/bin/env python3

import matplotlib.pyplot as plt
import csv
import os

# make figures dir
if not os.path.exists('../../figures'):
   os.makedirs('../../figures')

# open results file
with open('../../data/result.csv') as csvfile:
    reader = csv.reader(csvfile)
    rows = [row for row in reader]
    rows = rows[1:]
    for row in rows:
        row[8] = int(row[8])
        row[9] = int(row[9])
        row[10] = int(row[10])
    
    # drop error rows (-1 and -2)
    rows = [row for row in rows if row[8]>0 and row[9]>0 and row[10]>0]

gitmerge = [row[8] for row in rows]
spork = [row[9] for row in rows]
intellimerge = [row[10] for row in rows]

gitmergeincorrect = sum(val in [3,5,126] for val in gitmerge)
gitmergecorrect = sum(val == 2 for val in gitmerge)
gitmergeunhandled = sum(val == 1 for val in gitmerge)
gitmergefailure = sum(val in [6,124] for val in gitmerge)

sporkincorrect = sum(val in [3,5,126] for val in spork)
sporkcorrect = sum(val == 2 for val in spork)
sporkunhandled = sum(val == 1 for val in spork)
sporkfailure = sum(val in [6,124] for val in spork)

intellimergeincorrect = sum(val in [3,5,126] for val in intellimerge)
intellimergecorrect = sum(val == 2 for val in intellimerge)
intellimergeunhandled = sum(val == 1 for val in intellimerge)
intellimergefailure = sum(val in [6,124] for val in intellimerge)

# figure 1 (stacked area)
tools = ['Git Merge', 'Spork', 'IntelliMerge']
incorrect = [gitmergeincorrect, sporkincorrect, intellimergeincorrect]
unhandled = [gitmergeunhandled, sporkunhandled, intellimergeunhandled]
correct = [gitmergecorrect, sporkcorrect, intellimergecorrect]
failure = [gitmergefailure, sporkfailure, intellimergefailure]

fig, ax = plt.subplots()

ax.bar(tools, incorrect, label='Incorrect', color='#1F77B4')
ax.bar(tools, unhandled, bottom=incorrect, label='Unhandled', color='#FF7F0E')
ax.bar(tools, correct, label='Correct', bottom=[incorrect[i]+unhandled[i] for i in range(len(tools))], color='#2CA02C')

ax.set_ylabel('# of merges')
handles, labels = ax.get_legend_handles_labels()
ax.legend(reversed(handles), reversed(labels))

plt.savefig('../../figures/stacked.pdf')

# table 1 (overall results)
template = """\\begin{{tabular}}{{c|c c|c c|c c}} 
         Tool & 
         \multicolumn{{2}}{{|c|}}{{Correct Merges}} & 
         \multicolumn{{2}}{{|c|}}{{Unhandled Merges}} &
         \multicolumn{{2}}{{|c}}{{Incorrect Merges}}\\\\
         \hline
         & \# & \% & \# & \% & \# & \%\\\\ 
         Git Merge & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
         Spork & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
         IntelliMerge & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
    \end{{tabular}}"""

total = len(rows)
args = []
for i in range(len(tools)):
    args.append(correct[i])
    args.append(100*correct[i]/total)
    args.append(unhandled[i])
    args.append(100*unhandled[i]/total)
    args.append(incorrect[i])
    args.append(100*incorrect[i]/total)

table = template.format(*args)

with open('../../figures/table1.txt', 'w') as file:
    file.write(table)

# table 2 (by merge source)
template2 = """\\begin{{tabular}}{{c|c c c c|c c c c|c c c c}} 
         Tool & 
         \multicolumn{{4}}{{|c|}}{{Correct Merges}} & 
         \multicolumn{{4}}{{|c|}}{{Unhandled Merges}} &
         \multicolumn{{4}}{{|c|}}{{Incorrect Merges}}\\\\
         &
         \multicolumn{{2}}{{|c}}{{Main Branch}} & 
         \multicolumn{{2}}{{c|}}{{Feature Branch}} &
         \multicolumn{{2}}{{|c}}{{Main Branch}} & 
         \multicolumn{{2}}{{c|}}{{Feature Branch}} &
         \multicolumn{{2}}{{|c}}{{Main Branch}} & 
         \multicolumn{{2}}{{c|}}{{Feature Branch}} &
         \hline
         & \# & \% & \# & \% & \# & \% & \# & \% & \# & \% & \# & \%\\\\ 
         Git Merge & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
         Spork & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
         IntelliMerge & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\% & {} & {:.2f}\%\\\\
    \end{{tabular}}"""

main = [row for row in rows if row[3] in ['main','master']]
feature = [row for row in rows if row[3] not in ['main','master']]

gitmergem = [row[8] for row in main]
sporkm = [row[9] for row in main]
intellimergem = [row[10] for row in main]
gitmergef = [row[8] for row in feature]
sporkf = [row[9] for row in feature]
intellimergef = [row[10] for row in feature]
m = [gitmergem, sporkm, intellimergem]
f = [gitmergef, sporkf, intellimergef]

args = []
for i in range(len(tools)):
    correct = sum(val == 2 for val in m[i])
    args.append(correct)
    args.append(100*correct/len(main))
    correct = sum(val == 2 for val in f[i])
    args.append(correct)
    args.append(100*correct/len(feature))

    unhandled = sum(val == 1 for val in m[i])
    args.append(unhandled)
    args.append(100*unhandled/len(main))
    unhandled = sum(val == 1 for val in f[i])
    args.append(unhandled)
    args.append(100*unhandled/len(feature))

    incorrect = sum(val in [3,5,126] for val in m[i])
    args.append(incorrect)
    args.append(100*incorrect/len(main))
    incorrect = sum(val in [3,5,126] for val in f[i])
    args.append(incorrect)
    args.append(100*incorrect/len(feature))

table2 = template2.format(*args)

with open('../../figures/table2.txt', 'w') as file:
    file.write(table2)
