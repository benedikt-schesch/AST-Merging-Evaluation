#!/usr/bin/env python3

import matplotlib.pyplot as plt

labels = ['IntelliMerge', 'Spork', 'Git Merge', 'Commit History']
incorrect = [200, 350, 200, 300]
unhandled = [300, 250, 500, 0]
correct = [500, 400, 300, 700]

fig, ax = plt.subplots()

ax.bar(labels, incorrect, label='Incorrect')
ax.bar(labels, unhandled, bottom=incorrect, label='Unhandled')
ax.bar(labels, correct, bottom=[incorrect[i]+unhandled[i] for i in range(len(labels))], label='Correct')

ax.set_ylabel('# of merges')
ax.legend()

plt.show()
