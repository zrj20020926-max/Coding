import sys
lines = sys.stdin.buffer.read().splitlines()
n, q = map(int, lines[0].split()); parent = list(range(n)); size = [1]*n
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
out = []
for line in lines[1:1+q]:
    op, a, b = line.split(); a, b = int(a)-1, int(b)-1
    ra, rb = find(a), find(b)
    if op == b'U':
        if ra != rb:
            if size[ra] < size[rb]: ra, rb = rb, ra
            parent[rb] = ra; size[ra] += size[rb]
    else: out.append("YES" if ra == rb else "NO")
print("\n".join(out))
