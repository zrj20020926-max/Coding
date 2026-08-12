import sys
data=list(map(int,sys.stdin.buffer.read().split())); n,k=data[0],data[1]; a=sorted(data[2:])
def count(limit):
    total=left=0
    for right,value in enumerate(a):
        while value-a[left]>limit:left+=1
        total+=right-left
    return total
lo,hi=0,a[-1]-a[0]
while lo<hi:
    mid=(lo+hi)//2
    if count(mid)>=k:hi=mid
    else:lo=mid+1
print(lo)
