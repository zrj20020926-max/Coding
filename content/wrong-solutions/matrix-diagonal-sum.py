data = list(map(int, open(0).read().split()))
n, values = data[0], data[1:]
print(sum(values[i*n+i] + values[i*n+n-1-i] for i in range(n)))
