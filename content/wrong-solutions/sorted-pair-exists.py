data = list(map(int, open(0).read().split()))
n, target, values = data[0], data[1], data[2:]
print("YES" if any(value * 2 == target for value in values) else "NO")
