import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, capacity = next(it), next(it); dp = [0]*(capacity+1)
for _ in range(n):
    weight, value = next(it), next(it)
    for current in range(capacity, weight-1, -1): dp[current] = max(dp[current], dp[current-weight]+value)
print(dp[capacity])
