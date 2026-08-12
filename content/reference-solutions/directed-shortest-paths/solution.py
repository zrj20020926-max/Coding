import sys, heapq
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m, source = next(it), next(it), next(it)-1
graph = [[] for _ in range(n)]
for _ in range(m):
    u, v, w = next(it)-1, next(it)-1, next(it); graph[u].append((v,w))
inf = 10**30; dist = [inf]*n; dist[source] = 0; heap = [(0,source)]
while heap:
    d, u = heapq.heappop(heap)
    if d != dist[u]: continue
    for v, w in graph[u]:
        nd = d+w
        if nd < dist[v]: dist[v] = nd; heapq.heappush(heap,(nd,v))
print(" ".join(str(x) if x < inf else "-1" for x in dist))
