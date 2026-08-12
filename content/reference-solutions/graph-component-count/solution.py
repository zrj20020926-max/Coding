import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
graph = [[] for _ in range(n)]
for _ in range(m):
    u, v = next(it)-1, next(it)-1; graph[u].append(v); graph[v].append(u)
seen = [False]*n; answer = 0
for root in range(n):
    if seen[root]: continue
    answer += 1; seen[root] = True; stack = [root]
    while stack:
        node = stack.pop()
        for nxt in graph[node]:
            if not seen[nxt]: seen[nxt] = True; stack.append(nxt)
print(answer)
