import sys
lines = sys.stdin.buffer.read().decode().splitlines()
rows = []
for index, line in enumerate(lines[1:]):
    name, score = line.split()
    rows.append((name, int(score), index))
rows.sort(key=lambda item: (-item[1], item[2]))
print("\n".join(f"{name} {score}" for name, score, _ in rows))
