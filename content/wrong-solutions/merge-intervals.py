data = iter(map(int, open(0).read().split()))
n = next(data); intervals = sorted((next(data), next(data)) for _ in range(n)); merged = []
for left, right in intervals:
    if not merged or left >= merged[-1][1]: merged.append([left, right])
    else: merged[-1][1] = max(merged[-1][1], right)
print(len(merged)); print(*[f"{left} {right}" for left, right in merged], sep="\n")
