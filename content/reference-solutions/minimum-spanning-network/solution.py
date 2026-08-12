import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it); edges = []
for _ in range(m):
    u, v, w = next(it)-1, next(it)-1, next(it); edges.append((w, u, v))
edges.sort()
parent = list(range(n)); size = [1]*n
def find(x):
    while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
    return x
answer = used = 0
for w, u, v in edges:
    ru, rv = find(u), find(v)
    if ru != rv:
        if size[ru] < size[rv]: ru, rv = rv, ru
        parent[rv] = ru; size[ru] += size[rv]; answer += w; used += 1
print(answer if used == n-1 else -1)
