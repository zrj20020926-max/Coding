import bisect
data = list(map(int, open(0).read().split()))
n, target, values = data[0], data[1], data[2:]
position = bisect.bisect_right(values, target)
print(position if position and values[position - 1] == target else -1)
