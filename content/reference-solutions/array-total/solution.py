import sys
data = list(map(int, sys.stdin.buffer.read().split()))
print(sum(data[1:1 + data[0]]))
