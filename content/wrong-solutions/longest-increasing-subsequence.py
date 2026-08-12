import bisect
data = list(map(int, open(0).read().split())); tails = []
for value in data[1:]:
    position = bisect.bisect_right(tails, value)
    if position == len(tails): tails.append(value)
    else: tails[position] = value
print(len(tails))
