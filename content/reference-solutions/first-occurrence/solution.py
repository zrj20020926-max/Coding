import sys, bisect
data = list(map(int, sys.stdin.buffer.read().split()))
n, target = data[0], data[1]
a = data[2:2+n]
i = bisect.bisect_left(a, target)
print(i + 1 if i < n and a[i] == target else -1)
