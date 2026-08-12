import sys
data = list(map(int, sys.stdin.buffer.read().split()))
n, a = data[0], data[1:]
last = {}
left = answer = 0
for right, value in enumerate(a):
    left = max(left, last.get(value, -1) + 1)
    last[value] = right
    answer = max(answer, right - left + 1)
print(answer)
