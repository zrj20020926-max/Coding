import sys
from collections import deque
lines = sys.stdin.buffer.read().splitlines()
queue = deque()
out = []
for raw in lines[1:]:
    parts = raw.split()
    op = parts[0]
    if op == b"push": queue.append(int(parts[1]))
    elif op == b"pop": out.append(str(queue.popleft()) if queue else "EMPTY")
    elif op == b"front": out.append(str(queue[0]) if queue else "EMPTY")
    else: out.append(str(len(queue)))
print("\n".join(out))
