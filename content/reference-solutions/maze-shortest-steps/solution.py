import sys
from collections import deque
lines = sys.stdin.buffer.read().splitlines()
n, m = map(int, lines[0].split())
grid = [row.decode() for row in lines[1:1+n]]
start = end = None
for i, row in enumerate(grid):
    for j, ch in enumerate(row):
        if ch == 'S': start = (i,j)
        elif ch == 'T': end = (i,j)
dist = [[-1]*m for _ in range(n)]; dist[start[0]][start[1]] = 0
queue = deque([start])
while queue:
    x, y = queue.popleft()
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < n and 0 <= ny < m and grid[nx][ny] != '#' and dist[nx][ny] < 0:
            dist[nx][ny] = dist[x][y] + 1; queue.append((nx,ny))
print(dist[end[0]][end[1]])
