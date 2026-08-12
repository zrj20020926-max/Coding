import sys, heapq
it = iter(map(int, sys.stdin.buffer.read().split())); n, m = next(it), next(it)
grid = [[next(it) for _ in range(m)] for _ in range(n)]
inf = 10**30; dist = [[inf]*m for _ in range(n)]; dist[0][0] = grid[0][0]; heap = [(grid[0][0],0,0)]
while heap:
    d,x,y = heapq.heappop(heap)
    if d != dist[x][y]: continue
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx,ny=x+dx,y+dy
        if 0<=nx<n and 0<=ny<m and d+grid[nx][ny]<dist[nx][ny]:
            dist[nx][ny]=d+grid[nx][ny]; heapq.heappush(heap,(dist[nx][ny],nx,ny))
print(dist[-1][-1])
