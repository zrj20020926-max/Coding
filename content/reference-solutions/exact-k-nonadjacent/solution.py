import sys
data=list(map(int,sys.stdin.buffer.read().split())); n,k=data[0],data[1]; a=data[2:]
neg=-10**30; skip=[0]+[neg]*k; take=[neg]*(k+1)
for value in a:
    new_skip=[max(skip[j],take[j]) for j in range(k+1)]; new_take=[neg]*(k+1)
    for j in range(1,k+1): new_take[j]=skip[j-1]+value if skip[j-1]>neg else neg
    skip,take=new_skip,new_take
print(max(skip[k],take[k]))
