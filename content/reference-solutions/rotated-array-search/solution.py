import sys
data = list(map(int, sys.stdin.buffer.read().split()))
n, target, a = data[0], data[1], data[2:]
left, right = 0, n - 1
answer = -1
while left <= right:
    mid = (left + right) // 2
    if a[mid] == target: answer = mid + 1; break
    if a[left] <= a[mid]:
        if a[left] <= target < a[mid]: right = mid - 1
        else: left = mid + 1
    else:
        if a[mid] < target <= a[right]: left = mid + 1
        else: right = mid - 1
print(answer)
