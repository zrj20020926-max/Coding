import sys
from collections import deque
lines = sys.stdin.buffer.read().splitlines()
n, m = map(int, lines[0].split())
grid = [bytearray(row.strip()) for row in lines[1:1+n]]
answer = 0
for i in range(n):
    for j in range(m):
        if grid[i][j] != 49: continue
        answer += 1; grid[i][j] = 48; queue = deque([(i, j)])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = x+dx, y+dy
                if 0 <= nx < n and 0 <= ny < m and grid[nx][ny] == 49:
                    grid[nx][ny] = 48; queue.append((nx, ny))
print(answer)
