data = open(0).read().split(); n, m = map(int, data[:2]); grid = [list(row) for row in data[2:]]; answer = 0
for i in range(n):
    for j in range(m):
        if grid[i][j] != "1": continue
        answer += 1; grid[i][j] = "0"; stack = [(i,j)]
        while stack:
            x,y=stack.pop()
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                a,b=x+dx,y+dy
                if 0<=a<n and 0<=b<m and grid[a][b]=="1": grid[a][b]="0";stack.append((a,b))
print(answer)
