import sys
it=iter(map(int,sys.stdin.buffer.read().split())); length,m=next(it),next(it); intervals=[(next(it),next(it),next(it)) for _ in range(m)]
inf=10**30; dp=[inf]*(length+1);dp[0]=0
for covered in range(length):
    if dp[covered]>=inf:continue
    for left,right,cost in intervals:
        if left<=covered<right:dp[min(length,right)]=min(dp[min(length,right)],dp[covered]+cost)
print(dp[length] if dp[length]<inf else -1)
