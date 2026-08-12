import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n = next(it); events = sorted((next(it), next(it)) for _ in range(n))
events.sort(key=lambda item: (item[1], item[0]))
answer = 0; last_end = -10**30
for start, end in events:
    if start >= last_end: answer += 1; last_end = end
print(answer)
