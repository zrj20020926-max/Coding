import sys
a = sys.stdin.buffer.readline().rstrip(b"\r\n").decode(); b = sys.stdin.buffer.readline().rstrip(b"\r\n").decode()
previous = list(range(len(b)+1))
for i, ca in enumerate(a, 1):
    current = [i]
    for j, cb in enumerate(b, 1): current.append(min(current[-1]+1, previous[j]+1, previous[j-1]+(ca!=cb)))
    previous = current
print(previous[-1])
