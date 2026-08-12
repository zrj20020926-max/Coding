import sys
data = list(map(int, sys.stdin.buffer.read().split()))
n, target = data[0], data[1]
a = data[2:2+n]
i, j = 0, n - 1
while i < j:
    value = a[i] + a[j]
    if value == target:
        print("YES")
        break
    if value < target:
        i += 1
    else:
        j -= 1
else:
    print("NO")
