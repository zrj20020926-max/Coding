import sys
data = list(map(int, sys.stdin.buffer.read().split()))
n, target, coins = data[0], data[1], data[2:]
inf = target + 1; dp = [0] + [inf]*target
for amount in range(1, target+1):
    for coin in coins:
        if coin <= amount: dp[amount] = min(dp[amount], dp[amount-coin]+1)
print(dp[target] if dp[target] < inf else -1)
