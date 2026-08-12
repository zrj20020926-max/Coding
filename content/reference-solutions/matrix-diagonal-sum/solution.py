import sys
data = list(map(int, sys.stdin.buffer.read().split()))
n, values = data[0], data[1:]
answer = 0
for i in range(n):
    answer += values[i*n+i]
    if i != n-1-i: answer += values[i*n+n-1-i]
print(answer)
