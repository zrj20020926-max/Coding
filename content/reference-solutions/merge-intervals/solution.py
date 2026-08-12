import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n = next(it)
intervals = sorted((next(it), next(it)) for _ in range(n))
merged = []
for left, right in intervals:
    if not merged or left > merged[-1][1]: merged.append([left, right])
    else: merged[-1][1] = max(merged[-1][1], right)
print(len(merged))
print("\n".join(f"{left} {right}" for left, right in merged))
