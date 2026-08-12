import sys
from collections import Counter
it = iter(map(int, sys.stdin.buffer.read().split()))
n, q = next(it), next(it)
counts = Counter(next(it) for _ in range(n))
print("\n".join(str(counts[next(it)]) for _ in range(q)))
