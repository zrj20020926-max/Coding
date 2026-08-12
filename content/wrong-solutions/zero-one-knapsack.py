it = iter(map(int, open(0).read().split())); n, capacity = next(it), next(it); dp = [0]*(capacity+1)
for _ in range(n):
    weight, value = next(it), next(it)
    for current in range(weight, capacity+1): dp[current] = max(dp[current], dp[current-weight]+value)
print(dp[capacity])
