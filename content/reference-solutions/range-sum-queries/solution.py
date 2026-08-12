import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, q = next(it), next(it)
prefix = [0]
for _ in range(n): prefix.append(prefix[-1] + next(it))
print("\n".join(str((lambda l, r: prefix[r] - prefix[l - 1])(next(it), next(it))) for _ in range(q)))
