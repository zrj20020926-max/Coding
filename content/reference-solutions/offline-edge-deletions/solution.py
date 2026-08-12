import sys
lines=sys.stdin.buffer.read().splitlines(); n,m,q=map(int,lines[0].split()); edges=[tuple(map(lambda x:int(x)-1,line.split())) for line in lines[1:1+m]]
ops=[]; deleted=set()
for line in lines[1+m:1+m+q]:
    p=line.split()
    if p[0]==b'D': idx=int(p[1])-1; ops.append(('D',idx)); deleted.add(idx)
    else: ops.append(('Q',int(p[1])-1,int(p[2])-1))
parent=list(range(n)); size=[1]*n
def find(x):
    while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
    return x
def union(a,b):
    a,b=find(a),find(b)
    if a==b:return
    if size[a]<size[b]:a,b=b,a
    parent[b]=a;size[a]+=size[b]
for i,(a,b) in enumerate(edges):
    if i not in deleted: union(a,b)
out=[]
for op in reversed(ops):
    if op[0]=='D': union(*edges[op[1]])
    else: out.append('YES' if find(op[1])==find(op[2]) else 'NO')
print("\n".join(reversed(out)))
