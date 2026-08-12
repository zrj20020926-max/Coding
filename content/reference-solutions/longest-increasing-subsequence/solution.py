import sys, bisect
data = list(map(int, sys.stdin.buffer.read().split())); a = data[1:]
tails = []
for value in a:
    index = bisect.bisect_left(tails, value)
    if index == len(tails): tails.append(value)
    else: tails[index] = value
print(len(tails))
