from __future__ import annotations

import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RANDOM_SEED = 20260812
SCENARIOS = (
    ("minimum_boundary", "最小边界"),
    ("normal", "普通情况"),
    ("duplicates", "重复元素"),
    ("special_structure", "特殊结构"),
    ("performance", "极值或性能压力"),
    ("counterexample", "常见错误实现的反例"),
)
SCORES = (10, 15, 15, 20, 20, 20)


@dataclass(frozen=True)
class ProblemSpec:
    slug: str
    title: str
    difficulty: str
    tags: tuple[str, ...]
    story: str
    input_description: str
    output_description: str
    constraints: str
    sample_input: str
    sample_explanation: str
    time_limit_ms: int
    memory_limit_mb: int
    cases: tuple[str, ...]


PYTHON_SOLUTIONS: dict[str, str] = {
    "a-plus-b": '''import sys
a, b = map(int, sys.stdin.buffer.read().split())
print(a + b)
''',
    "array-total": '''import sys
data = list(map(int, sys.stdin.buffer.read().split()))
print(sum(data[1:1 + data[0]]))
''',
    "reverse-line": '''import sys
s = sys.stdin.buffer.readline().rstrip(b"\\r\\n").decode()
print(s[::-1])
''',
    "frequency-queries": '''import sys
from collections import Counter
it = iter(map(int, sys.stdin.buffer.read().split()))
n, q = next(it), next(it)
counts = Counter(next(it) for _ in range(n))
print("\\n".join(str(counts[next(it)]) for _ in range(q)))
''',
    "sorted-pair-exists": '''import sys
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
''',
    "balanced-brackets": '''import sys
s = sys.stdin.buffer.readline().strip().decode()
stack = []
pairs = {')': '(', ']': '[', '}': '{'}
for ch in s:
    if ch in "([{":
        stack.append(ch)
    elif not stack or stack.pop() != pairs[ch]:
        print("NO")
        break
else:
    print("YES" if not stack else "NO")
''',
    "queue-commands": '''import sys
from collections import deque
lines = sys.stdin.buffer.read().splitlines()
queue = deque()
out = []
for raw in lines[1:]:
    parts = raw.split()
    op = parts[0]
    if op == b"push": queue.append(int(parts[1]))
    elif op == b"pop": out.append(str(queue.popleft()) if queue else "EMPTY")
    elif op == b"front": out.append(str(queue[0]) if queue else "EMPTY")
    else: out.append(str(len(queue)))
print("\\n".join(out))
''',
    "first-occurrence": '''import sys, bisect
data = list(map(int, sys.stdin.buffer.read().split()))
n, target = data[0], data[1]
a = data[2:2+n]
i = bisect.bisect_left(a, target)
print(i + 1 if i < n and a[i] == target else -1)
''',
    "stable-score-sort": '''import sys
lines = sys.stdin.buffer.read().decode().splitlines()
rows = []
for index, line in enumerate(lines[1:]):
    name, score = line.split()
    rows.append((name, int(score), index))
rows.sort(key=lambda item: (-item[1], item[2]))
print("\\n".join(f"{name} {score}" for name, score, _ in rows))
''',
    "matrix-diagonal-sum": '''import sys
data = list(map(int, sys.stdin.buffer.read().split()))
n, values = data[0], data[1:]
answer = 0
for i in range(n):
    answer += values[i*n+i]
    if i != n-1-i: answer += values[i*n+n-1-i]
print(answer)
''',
    "longest-unique-segment": '''import sys
data = list(map(int, sys.stdin.buffer.read().split()))
n, a = data[0], data[1:]
last = {}
left = answer = 0
for right, value in enumerate(a):
    left = max(left, last.get(value, -1) + 1)
    last[value] = right
    answer = max(answer, right - left + 1)
print(answer)
''',
    "range-sum-queries": '''import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, q = next(it), next(it)
prefix = [0]
for _ in range(n): prefix.append(prefix[-1] + next(it))
print("\\n".join(str(prefix[next(it)] - prefix[(lambda x: x)(next(it)) - 1]) for _ in range(q)))
'''.replace("prefix[next(it)] - prefix[(lambda x: x)(next(it)) - 1]", "(lambda l, r: prefix[r] - prefix[l - 1])(next(it), next(it))"),
    "merge-intervals": '''import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n = next(it)
intervals = sorted((next(it), next(it)) for _ in range(n))
merged = []
for left, right in intervals:
    if not merged or left > merged[-1][1]: merged.append([left, right])
    else: merged[-1][1] = max(merged[-1][1], right)
print(len(merged))
print("\\n".join(f"{left} {right}" for left, right in merged))
''',
    "rotated-array-search": '''import sys
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
''',
    "island-count": '''import sys
from collections import deque
lines = sys.stdin.buffer.read().splitlines()
n, m = map(int, lines[0].split())
grid = [bytearray(row.strip()) for row in lines[1:1+n]]
answer = 0
for i in range(n):
    for j in range(m):
        if grid[i][j] != 49: continue
        answer += 1; grid[i][j] = 48; queue = deque([(i, j)])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = x+dx, y+dy
                if 0 <= nx < n and 0 <= ny < m and grid[nx][ny] == 49:
                    grid[nx][ny] = 48; queue.append((nx, ny))
print(answer)
''',
    "maze-shortest-steps": '''import sys
from collections import deque
lines = sys.stdin.buffer.read().splitlines()
n, m = map(int, lines[0].split())
grid = [row.decode() for row in lines[1:1+n]]
start = end = None
for i, row in enumerate(grid):
    for j, ch in enumerate(row):
        if ch == 'S': start = (i,j)
        elif ch == 'T': end = (i,j)
dist = [[-1]*m for _ in range(n)]; dist[start[0]][start[1]] = 0
queue = deque([start])
while queue:
    x, y = queue.popleft()
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < n and 0 <= ny < m and grid[nx][ny] != '#' and dist[nx][ny] < 0:
            dist[nx][ny] = dist[x][y] + 1; queue.append((nx,ny))
print(dist[end[0]][end[1]])
''',
    "graph-component-count": '''import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it)
graph = [[] for _ in range(n)]
for _ in range(m):
    u, v = next(it)-1, next(it)-1; graph[u].append(v); graph[v].append(u)
seen = [False]*n; answer = 0
for root in range(n):
    if seen[root]: continue
    answer += 1; seen[root] = True; stack = [root]
    while stack:
        node = stack.pop()
        for nxt in graph[node]:
            if not seen[nxt]: seen[nxt] = True; stack.append(nxt)
print(answer)
''',
    "union-find-queries": '''import sys
lines = sys.stdin.buffer.read().splitlines()
n, q = map(int, lines[0].split()); parent = list(range(n)); size = [1]*n
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
out = []
for line in lines[1:1+q]:
    op, a, b = line.split(); a, b = int(a)-1, int(b)-1
    ra, rb = find(a), find(b)
    if op == b'U':
        if ra != rb:
            if size[ra] < size[rb]: ra, rb = rb, ra
            parent[rb] = ra; size[ra] += size[rb]
    else: out.append("YES" if ra == rb else "NO")
print("\\n".join(out))
''',
    "directed-shortest-paths": '''import sys, heapq
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m, source = next(it), next(it), next(it)-1
graph = [[] for _ in range(n)]
for _ in range(m):
    u, v, w = next(it)-1, next(it)-1, next(it); graph[u].append((v,w))
inf = 10**30; dist = [inf]*n; dist[source] = 0; heap = [(0,source)]
while heap:
    d, u = heapq.heappop(heap)
    if d != dist[u]: continue
    for v, w in graph[u]:
        nd = d+w
        if nd < dist[v]: dist[v] = nd; heapq.heappush(heap,(nd,v))
print(" ".join(str(x) if x < inf else "-1" for x in dist))
''',
    "minimum-spanning-network": '''import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, m = next(it), next(it); edges = []
for _ in range(m):
    u, v, w = next(it)-1, next(it)-1, next(it); edges.append((w, u, v))
edges.sort()
parent = list(range(n)); size = [1]*n
def find(x):
    while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
    return x
answer = used = 0
for w, u, v in edges:
    ru, rv = find(u), find(v)
    if ru != rv:
        if size[ru] < size[rv]: ru, rv = rv, ru
        parent[rv] = ru; size[ru] += size[rv]; answer += w; used += 1
print(answer if used == n-1 else -1)
''',
    "maximum-compatible-events": '''import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n = next(it); events = sorted((next(it), next(it)) for _ in range(n))
events.sort(key=lambda item: (item[1], item[0]))
answer = 0; last_end = -10**30
for start, end in events:
    if start >= last_end: answer += 1; last_end = end
print(answer)
''',
    "zero-one-knapsack": '''import sys
it = iter(map(int, sys.stdin.buffer.read().split()))
n, capacity = next(it), next(it); dp = [0]*(capacity+1)
for _ in range(n):
    weight, value = next(it), next(it)
    for current in range(capacity, weight-1, -1): dp[current] = max(dp[current], dp[current-weight]+value)
print(dp[capacity])
''',
    "minimum-coin-count": '''import sys
data = list(map(int, sys.stdin.buffer.read().split()))
n, target, coins = data[0], data[1], data[2:]
inf = target + 1; dp = [0] + [inf]*target
for amount in range(1, target+1):
    for coin in coins:
        if coin <= amount: dp[amount] = min(dp[amount], dp[amount-coin]+1)
print(dp[target] if dp[target] < inf else -1)
''',
    "longest-increasing-subsequence": '''import sys, bisect
data = list(map(int, sys.stdin.buffer.read().split())); a = data[1:]
tails = []
for value in a:
    index = bisect.bisect_left(tails, value)
    if index == len(tails): tails.append(value)
    else: tails[index] = value
print(len(tails))
''',
    "string-edit-distance": '''import sys
a = sys.stdin.buffer.readline().rstrip(b"\\r\\n").decode(); b = sys.stdin.buffer.readline().rstrip(b"\\r\\n").decode()
previous = list(range(len(b)+1))
for i, ca in enumerate(a, 1):
    current = [i]
    for j, cb in enumerate(b, 1): current.append(min(current[-1]+1, previous[j]+1, previous[j-1]+(ca!=cb)))
    previous = current
print(previous[-1])
''',
    "weighted-grid-route": '''import sys, heapq
it = iter(map(int, sys.stdin.buffer.read().split())); n, m = next(it), next(it)
grid = [[next(it) for _ in range(m)] for _ in range(n)]
inf = 10**30; dist = [[inf]*m for _ in range(n)]; dist[0][0] = grid[0][0]; heap = [(grid[0][0],0,0)]
while heap:
    d,x,y = heapq.heappop(heap)
    if d != dist[x][y]: continue
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx,ny=x+dx,y+dy
        if 0<=nx<n and 0<=ny<m and d+grid[nx][ny]<dist[nx][ny]:
            dist[nx][ny]=d+grid[nx][ny]; heapq.heappush(heap,(dist[nx][ny],nx,ny))
print(dist[-1][-1])
''',
    "exact-k-nonadjacent": '''import sys
data=list(map(int,sys.stdin.buffer.read().split())); n,k=data[0],data[1]; a=data[2:]
neg=-10**30; skip=[0]+[neg]*k; take=[neg]*(k+1)
for value in a:
    new_skip=[max(skip[j],take[j]) for j in range(k+1)]; new_take=[neg]*(k+1)
    for j in range(1,k+1): new_take[j]=skip[j-1]+value if skip[j-1]>neg else neg
    skip,take=new_skip,new_take
print(max(skip[k],take[k]))
''',
    "offline-edge-deletions": '''import sys
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
print("\\n".join(reversed(out)))
''',
    "kth-pair-distance": '''import sys
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
''',
    "minimum-cover-cost": '''import sys
it=iter(map(int,sys.stdin.buffer.read().split())); length,m=next(it),next(it); intervals=[(next(it),next(it),next(it)) for _ in range(m)]
inf=10**30; dp=[inf]*(length+1);dp[0]=0
for covered in range(length):
    if dp[covered]>=inf:continue
    for left,right,cost in intervals:
        if left<=covered<right:dp[min(length,right)]=min(dp[min(length,right)],dp[covered]+cost)
print(dp[length] if dp[length]<inf else -1)
''',
}


CPP_SOLUTIONS: dict[str, str] = {
    "a-plus-b": R'''#include <iostream>
using namespace std; int main(){long long a,b;if(cin>>a>>b)cout<<a+b<<'\n';}''',
    "array-total": R'''#include <iostream>
using namespace std; int main(){int n;cin>>n;long long s=0,x;while(n--){cin>>x;s+=x;}cout<<s<<'\n';}''',
    "reverse-line": R'''#include <algorithm>
#include <iostream>
#include <string>
using namespace std; int main(){string s;getline(cin,s);reverse(s.begin(),s.end());cout<<s<<'\n';}''',
    "frequency-queries": R'''#include <iostream>
#include <unordered_map>
using namespace std; int main(){ios::sync_with_stdio(false);cin.tie(nullptr);int n,q;cin>>n>>q;unordered_map<long long,int> c;long long x;while(n--){cin>>x;++c[x];}while(q--){cin>>x;cout<<c[x]<<'\n';}}''',
    "sorted-pair-exists": R'''#include <iostream>
#include <vector>
using namespace std; int main(){int n;long long t;cin>>n>>t;vector<long long>a(n);for(auto&x:a)cin>>x;int l=0,r=n-1;while(l<r){auto s=a[l]+a[r];if(s==t){cout<<"YES\n";return 0;}s<t?++l:--r;}cout<<"NO\n";}''',
    "balanced-brackets": R'''#include <iostream>
#include <stack>
#include <string>
using namespace std; int main(){string s,t;cin>>s;for(char c:s){if(c=='('||c=='['||c=='{')t+=c;else{char need=c==')'?'(':c==']'?'[':'{';if(t.empty()||t.back()!=need){cout<<"NO\n";return 0;}t.pop_back();}}cout<<(t.empty()?"YES\n":"NO\n");}''',
    "queue-commands": R'''#include <iostream>
#include <queue>
#include <string>
using namespace std; int main(){ios::sync_with_stdio(false);int q;cin>>q;queue<long long>a;while(q--){string op;cin>>op;if(op=="push"){long long x;cin>>x;a.push(x);}else if(op=="pop"){if(a.empty())cout<<"EMPTY\n";else{cout<<a.front()<<'\n';a.pop();}}else if(op=="front")cout<<(a.empty()?"EMPTY":to_string(a.front()))<<'\n';else cout<<a.size()<<'\n';}}''',
    "first-occurrence": R'''#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n;long long t;cin>>n>>t;vector<long long>a(n);for(auto&x:a)cin>>x;auto it=lower_bound(a.begin(),a.end(),t);cout<<(it!=a.end()&&*it==t?it-a.begin()+1:-1)<<'\n';}''',
    "stable-score-sort": R'''#include <algorithm>
#include <iostream>
#include <string>
#include <vector>
using namespace std;struct R{string n;int s,i;};int main(){int n;cin>>n;vector<R>a(n);for(int i=0;i<n;++i){cin>>a[i].n>>a[i].s;a[i].i=i;}stable_sort(a.begin(),a.end(),[](auto&x,auto&y){return x.s>y.s;});for(auto&r:a)cout<<r.n<<' '<<r.s<<'\n';}''',
    "matrix-diagonal-sum": R'''#include <iostream>
using namespace std;int main(){int n;cin>>n;long long ans=0,x;for(int i=0;i<n;++i)for(int j=0;j<n;++j){cin>>x;if(i==j||i+j==n-1)ans+=x;}cout<<ans<<'\n';}''',
    "longest-unique-segment": R'''#include <algorithm>
#include <iostream>
#include <unordered_map>
using namespace std;int main(){int n;cin>>n;unordered_map<long long,int>last;int l=0,ans=0;for(int r=0;r<n;++r){long long x;cin>>x;if(last.count(x))l=max(l,last[x]+1);last[x]=r;ans=max(ans,r-l+1);}cout<<ans<<'\n';}''',
    "range-sum-queries": R'''#include <iostream>
#include <vector>
using namespace std;int main(){ios::sync_with_stdio(false);cin.tie(nullptr);int n,q;cin>>n>>q;vector<long long>p(n+1);for(int i=1;i<=n;++i){cin>>p[i];p[i]+=p[i-1];}while(q--){int l,r;cin>>l>>r;cout<<p[r]-p[l-1]<<'\n';}}''',
    "merge-intervals": R'''#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n;cin>>n;vector<pair<long long,long long>>a(n),b;for(auto&x:a)cin>>x.first>>x.second;sort(a.begin(),a.end());for(auto x:a)if(b.empty()||x.first>b.back().second)b.push_back(x);else b.back().second=max(b.back().second,x.second);cout<<b.size()<<'\n';for(auto x:b)cout<<x.first<<' '<<x.second<<'\n';}''',
    "rotated-array-search": R'''#include <iostream>
#include <vector>
using namespace std;int main(){int n;long long t;cin>>n>>t;vector<long long>a(n);for(auto&x:a)cin>>x;int l=0,r=n-1;while(l<=r){int m=(l+r)/2;if(a[m]==t){cout<<m+1<<'\n';return 0;}if(a[l]<=a[m]){if(a[l]<=t&&t<a[m])r=m-1;else l=m+1;}else{if(a[m]<t&&t<=a[r])l=m+1;else r=m-1;}}cout<<-1<<'\n';}''',
    "island-count": R'''#include <iostream>
#include <queue>
#include <string>
#include <vector>
using namespace std;int main(){int n,m;cin>>n>>m;vector<string>g(n);for(auto&s:g)cin>>s;int ans=0,dx[4]={1,-1,0,0},dy[4]={0,0,1,-1};for(int i=0;i<n;++i)for(int j=0;j<m;++j)if(g[i][j]=='1'){++ans;queue<pair<int,int>>q;q.push({i,j});g[i][j]='0';while(!q.empty()){auto[x,y]=q.front();q.pop();for(int k=0;k<4;++k){int a=x+dx[k],b=y+dy[k];if(a>=0&&a<n&&b>=0&&b<m&&g[a][b]=='1'){g[a][b]='0';q.push({a,b});}}}}cout<<ans<<'\n';}''',
    "maze-shortest-steps": R'''#include <iostream>
#include <queue>
#include <string>
#include <vector>
using namespace std;int main(){int n,m;cin>>n>>m;vector<string>g(n);pair<int,int>s,t;for(int i=0;i<n;++i){cin>>g[i];for(int j=0;j<m;++j){if(g[i][j]=='S')s={i,j};if(g[i][j]=='T')t={i,j};}}vector<vector<int>>d(n,vector<int>(m,-1));queue<pair<int,int>>q;q.push(s);d[s.first][s.second]=0;int dx[4]={1,-1,0,0},dy[4]={0,0,1,-1};while(!q.empty()){auto[x,y]=q.front();q.pop();for(int k=0;k<4;++k){int a=x+dx[k],b=y+dy[k];if(a>=0&&a<n&&b>=0&&b<m&&g[a][b]!='#'&&d[a][b]<0){d[a][b]=d[x][y]+1;q.push({a,b});}}}cout<<d[t.first][t.second]<<'\n';}''',
    "graph-component-count": R'''#include <iostream>
#include <vector>
using namespace std;int main(){int n,m;cin>>n>>m;vector<vector<int>>g(n);while(m--){int u,v;cin>>u>>v;--u;--v;g[u].push_back(v);g[v].push_back(u);}vector<char>seen(n);int ans=0;for(int r=0;r<n;++r)if(!seen[r]){++ans;vector<int>s={r};seen[r]=1;while(!s.empty()){int u=s.back();s.pop_back();for(int v:g[u])if(!seen[v])seen[v]=1,s.push_back(v);}}cout<<ans<<'\n';}''',
    "union-find-queries": R'''#include <iostream>
#include <numeric>
#include <string>
#include <vector>
using namespace std;int main(){ios::sync_with_stdio(false);int n,q;cin>>n>>q;vector<int>p(n),s(n,1);iota(p.begin(),p.end(),0);auto find=[&](int x){while(p[x]!=x)x=p[x]=p[p[x]];return x;};while(q--){char op;int a,b;cin>>op>>a>>b;--a;--b;a=find(a);b=find(b);if(op=='U'){if(a!=b){if(s[a]<s[b])swap(a,b);p[b]=a;s[a]+=s[b];}}else cout<<(a==b?"YES\n":"NO\n");}}''',
    "directed-shortest-paths": R'''#include <functional>
#include <iostream>
#include <queue>
#include <vector>
using namespace std;int main(){int n,m,s;cin>>n>>m>>s;--s;vector<vector<pair<int,int>>>g(n);while(m--){int u,v,w;cin>>u>>v>>w;g[--u].push_back({--v,w});}const long long I=4e18;vector<long long>d(n,I);priority_queue<pair<long long,int>,vector<pair<long long,int>>,greater<pair<long long,int>>>q;d[s]=0;q.push({0,s});while(!q.empty()){auto[x,u]=q.top();q.pop();if(x!=d[u])continue;for(auto[v,w]:g[u])if(x+w<d[v]){d[v]=x+w;q.push({d[v],v});}}for(int i=0;i<n;++i)cout<<(d[i]==I?-1:d[i])<<(i+1==n?'\n':' ');}''',
    "minimum-spanning-network": R'''#include <algorithm>
#include <iostream>
#include <numeric>
#include <vector>
using namespace std;struct E{int u,v,w;};int main(){int n,m;cin>>n>>m;vector<E>e(m);for(auto&x:e){cin>>x.u>>x.v>>x.w;--x.u;--x.v;}sort(e.begin(),e.end(),[](auto&a,auto&b){return a.w<b.w;});vector<int>p(n),s(n,1);iota(p.begin(),p.end(),0);auto f=[&](int x){while(p[x]!=x)x=p[x]=p[p[x]];return x;};long long ans=0;int used=0;for(auto x:e){int a=f(x.u),b=f(x.v);if(a!=b){if(s[a]<s[b])swap(a,b);p[b]=a;s[a]+=s[b];ans+=x.w;++used;}}cout<<(used==n-1?ans:-1)<<'\n';}''',
    "maximum-compatible-events": R'''#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n;cin>>n;vector<pair<long long,long long>>a(n);for(auto&x:a)cin>>x.first>>x.second;sort(a.begin(),a.end(),[](auto&x,auto&y){return x.second!=y.second?x.second<y.second:x.first<y.first;});long long last=-(1LL<<60);int ans=0;for(auto[s,e]:a)if(s>=last){++ans;last=e;}cout<<ans<<'\n';}''',
    "zero-one-knapsack": R'''#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n,c;cin>>n>>c;vector<long long>d(c+1);while(n--){int w,v;cin>>w>>v;for(int x=c;x>=w;--x)d[x]=max(d[x],d[x-w]+v);}cout<<d[c]<<'\n';}''',
    "minimum-coin-count": R'''#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n,t;cin>>n>>t;vector<int>a(n),d(t+1,t+1);for(int&x:a)cin>>x;d[0]=0;for(int x=1;x<=t;++x)for(int c:a)if(c<=x)d[x]=min(d[x],d[x-c]+1);cout<<(d[t]>t?-1:d[t])<<'\n';}''',
    "longest-increasing-subsequence": R'''#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n;cin>>n;vector<long long>t;while(n--){long long x;cin>>x;auto it=lower_bound(t.begin(),t.end(),x);if(it==t.end())t.push_back(x);else*it=x;}cout<<t.size()<<'\n';}''',
    "string-edit-distance": R'''#include <algorithm>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>
using namespace std;int main(){string a,b;getline(cin,a);getline(cin,b);vector<int>p(b.size()+1),c;iota(p.begin(),p.end(),0);for(int i=1;i<=(int)a.size();++i){c.assign(b.size()+1,0);c[0]=i;for(int j=1;j<=(int)b.size();++j)c[j]=min({c[j-1]+1,p[j]+1,p[j-1]+(a[i-1]!=b[j-1])});p.swap(c);}cout<<p.back()<<'\n';}''',
    "weighted-grid-route": R'''#include <functional>
#include <iostream>
#include <queue>
#include <tuple>
#include <vector>
using namespace std;int main(){int n,m;cin>>n>>m;vector<vector<int>>a(n,vector<int>(m));for(auto&r:a)for(int&x:r)cin>>x;const long long I=4e18;vector<vector<long long>>d(n,vector<long long>(m,I));priority_queue<tuple<long long,int,int>,vector<tuple<long long,int,int>>,greater<tuple<long long,int,int>>>q;d[0][0]=a[0][0];q.push({d[0][0],0,0});int dx[4]={1,-1,0,0},dy[4]={0,0,1,-1};while(!q.empty()){auto[z,x,y]=q.top();q.pop();if(z!=d[x][y])continue;for(int k=0;k<4;++k){int u=x+dx[k],v=y+dy[k];if(u>=0&&u<n&&v>=0&&v<m&&z+a[u][v]<d[u][v]){d[u][v]=z+a[u][v];q.push({d[u][v],u,v});}}}cout<<d[n-1][m-1]<<'\n';}''',
    "exact-k-nonadjacent": R'''#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n,k;cin>>n>>k;const long long N=-(1LL<<60);vector<long long>s(k+1,N),t(k+1,N),ns,nt;s[0]=0;while(n--){long long x;cin>>x;ns=s;nt.assign(k+1,N);for(int j=0;j<=k;++j)ns[j]=max(s[j],t[j]);for(int j=1;j<=k;++j)if(s[j-1]>N)nt[j]=s[j-1]+x;s.swap(ns);t.swap(nt);}cout<<max(s[k],t[k])<<'\n';}''',
    "offline-edge-deletions": R'''#include <algorithm>
#include <iostream>
#include <numeric>
#include <string>
#include <tuple>
#include <vector>
using namespace std;int main(){int n,m,q;cin>>n>>m>>q;vector<pair<int,int>>e(m);for(auto&[a,b]:e){cin>>a>>b;--a;--b;}vector<tuple<char,int,int>>o;vector<char>d(m);while(q--){char c;int a,b=-1;cin>>c>>a;--a;if(c=='Q'){cin>>b;--b;}else d[a]=1;o.push_back({c,a,b});}vector<int>p(n),s(n,1);iota(p.begin(),p.end(),0);auto f=[&](int x){while(p[x]!=x)x=p[x]=p[p[x]];return x;};auto u=[&](int a,int b){a=f(a);b=f(b);if(a==b)return;if(s[a]<s[b])swap(a,b);p[b]=a;s[a]+=s[b];};for(int i=0;i<m;++i)if(!d[i])u(e[i].first,e[i].second);vector<string>ans;for(auto it=o.rbegin();it!=o.rend();++it){auto[c,a,b]=*it;if(c=='D')u(e[a].first,e[a].second);else ans.push_back(f(a)==f(b)?"YES":"NO");}reverse(ans.begin(),ans.end());for(auto&s:ans)cout<<s<<'\n';}''',
    "kth-pair-distance": R'''#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n;long long k;cin>>n>>k;vector<long long>a(n);for(auto&x:a)cin>>x;sort(a.begin(),a.end());auto count=[&](long long d){long long z=0;int l=0;for(int r=0;r<n;++r){while(a[r]-a[l]>d)++l;z+=r-l;}return z;};long long l=0,r=a.back()-a.front();while(l<r){long long m=(l+r)/2;if(count(m)>=k)r=m;else l=m+1;}cout<<l<<'\n';}''',
    "minimum-cover-cost": R'''#include <algorithm>
#include <iostream>
#include <tuple>
#include <vector>
using namespace std;int main(){int L,m;cin>>L>>m;vector<tuple<int,int,long long>>a(m);for(auto&[l,r,c]:a)cin>>l>>r>>c;const long long I=4e18;vector<long long>d(L+1,I);d[0]=0;for(int x=0;x<L;++x)if(d[x]<I)for(auto[l,r,c]:a)if(l<=x&&x<r)d[min(L,r)]=min(d[min(L,r)],d[x]+c);cout<<(d[L]==I?-1:d[L])<<'\n';}''',
}


def _grid_case(rows: list[str]) -> str:
    return f"{len(rows)} {len(rows[0])}\n" + "\n".join(rows) + "\n"


def _matrix_case(matrix: list[list[int]]) -> str:
    return f"{len(matrix)} {len(matrix[0])}\n" + "\n".join(
        " ".join(map(str, row)) for row in matrix
    ) + "\n"


def _array_case(values: list[int], prefix: str = "") -> str:
    return f"{prefix}{len(values)}\n" + " ".join(map(str, values)) + "\n"


def problem_specs() -> tuple[ProblemSpec, ...]:
    rng = random.Random(RANDOM_SEED)
    large_array = [rng.randint(-10**9, 10**9) for _ in range(20000)]
    unique_stress = [rng.randint(1, 5000) for _ in range(30000)]
    lis_stress = [rng.randint(-10**9, 10**9) for _ in range(30000)]
    weighted_grid = [[rng.randint(1, 1000) for _ in range(90)] for _ in range(90)]
    return (
        ProblemSpec("a-plus-b", "边界求和", "easy", ("basic-io", "math"),
            "读取两个整数，输出它们的和。结果可能超出 32 位有符号整数范围。",
            "一行包含两个整数 `a b`。", "输出一个整数 `a+b`。",
            "`-10^18 <= a,b <= 10^18`，且答案保证在 64 位有符号整数范围内。",
            "7 -3\n", "七与负三相加得到四。", 1000, 128,
            ("0 0\n", "7 -3\n", "5 5\n", "-8 -13\n", "1000000000000000000 -999999999999999999\n", "2147483647 1\n")),
        ProblemSpec("array-total", "长数组总和", "easy", ("basic-io", "array"),
            "给定一个整数数组，计算所有元素之和。需要使用足够大的整数类型保存答案。",
            "第一行一个整数 `n`，第二行 `n` 个整数。", "输出数组元素总和。",
            "`1 <= n <= 20000`，`-10^9 <= a_i <= 10^9`。",
            "5\n1 2 -3 4 5\n", "依次累加得到九。", 1000, 128,
            ("1\n0\n", "5\n1 2 -3 4 5\n", "6\n4 4 4 4 4 4\n", "4\n-5 -2 -9 -1\n", _array_case(large_array), "3\n1000000000 1000000000 1000000000\n")),
        ProblemSpec("reverse-line", "整行逆序", "easy", ("basic-io", "string"),
            "读取一整行可打印 ASCII 字符，将字符顺序完全反转。行内空格也是数据的一部分。",
            "一行非空字符串 `s`，首尾均不是空格。", "输出 `s` 的逐字符逆序结果。",
            "`1 <= |s| <= 200000`，字符为 ASCII 32 到 126。",
            "code arena\n", "空格保留在字符串中，逆序后位于对应位置。", 1000, 128,
            ("a\n", "code arena\n", "aaaaaa\n", "A man 2\n", ("abcXYZ09 "*20000).strip()+"\n", "ab cd\n")),
        ProblemSpec("frequency-queries", "频次查询表", "easy", ("hash-table", "array"),
            "建立数组元素的频次表，并回答每个查询值在数组中出现了多少次。",
            "第一行 `n q`，第二行 `n` 个整数，第三行 `q` 个查询整数。", "每个查询输出一行出现次数。",
            "`1 <= n,q <= 100000`，所有数绝对值不超过 `10^9`。",
            "6 3\n1 2 2 3 2 1\n2 4 1\n", "二出现三次，四未出现，一出现两次。", 1500, 256,
            ("1 1\n5\n5\n", "6 3\n1 2 2 3 2 1\n2 4 1\n", "8 3\n7 7 7 7 7 7 7 7\n7 0 -1\n", "5 4\n-1 0 1 -1 0\n-1 0 2 1\n", f"20000 3\n{' '.join(map(str, large_array))}\n0 1 -1\n", "5 3\n-1000000000 1000000000 0 0 0\n0 -1000000000 2\n")),
        ProblemSpec("sorted-pair-exists", "有序双数之和", "easy", ("two-pointers", "array"),
            "在非递减数组中判断是否存在两个不同位置的元素之和等于目标值。",
            "第一行 `n target`，第二行 `n` 个非递减整数。", "存在则输出 `YES`，否则输出 `NO`。",
            "`2 <= n <= 200000`，元素和目标值绝对值不超过 `10^18`。",
            "6 9\n1 2 3 4 7 10\n", "二与七的和为九。", 1000, 128,
            ("2 2\n1 1\n", "6 9\n1 2 3 4 7 10\n", "5 8\n4 4 4 4 4\n", "5 -9\n-8 -5 -4 0 2\n", f"20000 19999\n{' '.join(map(str, range(20000)))}\n", "3 10\n5 6 20\n")),
        ProblemSpec("balanced-brackets", "多类括号校验", "easy", ("stack", "string"),
            "判断只由圆括号、方括号和花括号组成的字符串是否正确匹配且嵌套。",
            "一行括号字符串。", "合法输出 `YES`，否则输出 `NO`。",
            "`1 <= |s| <= 200000`。",
            "{[()()]}\n", "每个右括号都与最近的同类左括号配对。", 1000, 128,
            ("()\n", "{[()()]}\n", "()()()\n", "(((())))\n", "("*100000+")"*100000+"\n", "([)]\n")),
        ProblemSpec("queue-commands", "窗口服务队列", "easy", ("queue", "simulation"),
            "维护一个先进先出的整数队列，按顺序执行入队、出队、查看队首和查询长度操作。",
            "第一行操作数 `q`。随后每行是 `push x`、`pop`、`front` 或 `size`。", "对后三类操作输出结果；空队列的 `pop/front` 输出 `EMPTY`。",
            "`1 <= q <= 100000`，`|x| <= 10^9`。",
            "7\npush 3\npush 5\nfront\npop\nsize\npop\npop\n", "队首先为三；弹出三后剩一个元素，最后一次弹出时队列为空。", 1200, 128,
            ("1\nsize\n", "7\npush 3\npush 5\nfront\npop\nsize\npop\npop\n", "6\npush 8\npush 8\nfront\npop\nfront\nsize\n", "5\npop\nfront\npush -1\npop\nsize\n", "10000\n"+"\n".join([f"push {i}" for i in range(5000)]+["pop"]*5000)+"\n", "4\npush 0\npop\nfront\nsize\n")),
        ProblemSpec("first-occurrence", "第一个目标位置", "easy", ("binary-search", "array"),
            "在非递减数组中查找目标值第一次出现的位置。",
            "第一行 `n target`，第二行 `n` 个非递减整数。", "输出一基位置；不存在输出 `-1`。",
            "`1 <= n <= 200000`，整数绝对值不超过 `10^9`。",
            "7 2\n-1 2 2 2 5 8 9\n", "目标值二第一次出现在第二个位置。", 1000, 128,
            ("1 5\n5\n", "7 2\n-1 2 2 2 5 8 9\n", "6 3\n3 3 3 3 3 3\n", "5 0\n1 2 3 4 5\n", f"20000 19999\n{' '.join(map(str, range(20000)))}\n", "4 1\n1 1 2 3\n")),
        ProblemSpec("stable-score-sort", "稳定成绩排序", "easy", ("sorting",),
            "按分数从高到低输出参赛者；分数相同时必须保持输入先后顺序。名字互不相同。",
            "第一行 `n`，随后每行一个不含空格的名字和分数。", "输出排序后的名字与分数。",
            "`1 <= n <= 100000`，名字长度不超过 20，`0 <= score <= 100`。",
            "4\nlin 80\nmei 95\nyu 80\nan 60\n", "九十五分最先；同为八十分的 lin 仍在 yu 前。", 1500, 256,
            ("1\na 0\n", "4\nlin 80\nmei 95\nyu 80\nan 60\n", "5\na 70\nb 70\nc 70\nd 70\ne 70\n", "4\na 100\nb 0\nc 99\nd 1\n", "10000\n"+"\n".join(f"u{i} {i%101}" for i in range(10000))+"\n", "3\nfirst 50\nsecond 100\nthird 50\n")),
        ProblemSpec("matrix-diagonal-sum", "交叉对角线之和", "easy", ("matrix", "basic-io"),
            "计算方阵主对角线与副对角线上所有不同单元格的和。奇数阶中心格只能计算一次。",
            "第一行 `n`，随后 `n` 行每行 `n` 个整数。", "输出交叉对角线元素和。",
            "`1 <= n <= 1000`，元素绝对值不超过 `10^9`。",
            "3\n1 2 3\n4 5 6\n7 8 9\n", "两条对角线为 1,5,9 与 3,5,7，中心五只计一次，总和二十五。", 1200, 128,
            ("1\n7\n", "3\n1 2 3\n4 5 6\n7 8 9\n", "2\n5 5\n5 5\n", "4\n1 0 0 2\n0 3 4 0\n0 5 6 0\n7 0 0 8\n", _matrix_case([[i*200+j for j in range(200)] for i in range(200)]).replace("200 200", "200", 1), "3\n1 0 1\n0 100 0\n1 0 1\n")),
        ProblemSpec("longest-unique-segment", "最长无重复片段", "medium", ("sliding-window", "hash-table"),
            "求数组中不含重复值的最长连续子数组长度。",
            "第一行 `n`，第二行 `n` 个整数。", "输出最长长度。",
            "`1 <= n <= 200000`，元素绝对值不超过 `10^9`。",
            "8\n1 2 3 2 4 5 4 6\n", "片段 1,2,3 长三，片段 2,4,5 长三，没有更长片段。", 1500, 256,
            ("1\n9\n", "8\n1 2 3 2 4 5 4 6\n", "7\n2 2 2 2 2 2 2\n", "8\n1 2 1 3 4 3 5 6\n", _array_case(unique_stress), "5\n1 2 3 1 2\n")),
        ProblemSpec("range-sum-queries", "静态区间求和", "medium", ("prefix-sum", "array"),
            "对一个不再修改的数组回答多个闭区间元素和查询。",
            "第一行 `n q`，第二行数组；随后 `q` 行给出一基下标 `l r`。", "每个查询输出一行区间和。",
            "`1 <= n,q <= 100000`，`1 <= l <= r <= n`，`|a_i| <= 10^9`。",
            "5 3\n2 -1 4 3 5\n1 3\n2 5\n4 4\n", "三个区间的和分别为五、十一、三。", 1200, 256,
            ("1 1\n5\n1 1\n", "5 3\n2 -1 4 3 5\n1 3\n2 5\n4 4\n", "5 2\n7 7 7 7 7\n1 5\n2 4\n", "6 3\n1 -1 1 -1 1 -1\n1 6\n2 5\n3 3\n", f"20000 2\n{' '.join(map(str, large_array))}\n1 20000\n100 19999\n", "3 2\n1000000000 1000000000 1000000000\n1 3\n2 2\n")),
        ProblemSpec("merge-intervals", "闭区间合并", "medium", ("interval", "sorting"),
            "合并所有相交或端点相接的闭区间，并按左端点递增输出。",
            "第一行 `n`，随后 `n` 行为 `l r`。", "先输出合并后数量，再逐行输出区间。",
            "`1 <= n <= 200000`，`-10^9 <= l <= r <= 10^9`。",
            "4\n1 3\n2 6\n8 10\n10 12\n", "前两个合并为 1 到 6，后两个在端点十相接，合并为 8 到 12。", 1500, 256,
            ("1\n0 0\n", "4\n1 3\n2 6\n8 10\n10 12\n", "4\n2 5\n2 5\n2 5\n2 5\n", "5\n1 10\n2 3\n4 5\n6 9\n10 12\n", "20000\n"+"\n".join(f"{i*2} {i*2+1}" for i in range(20000))+"\n", "3\n1 2\n2 3\n4 4\n")),
        ProblemSpec("rotated-array-search", "旋转数组定位", "medium", ("binary-search", "array"),
            "严格递增数组在某个位置旋转后形成新数组，查找目标值的位置。数组元素互不相同。",
            "第一行 `n target`，第二行旋转后的数组。", "输出一基位置；不存在输出 `-1`。",
            "`1 <= n <= 200000`，元素绝对值不超过 `10^9`。",
            "7 2\n6 7 9 1 2 3 5\n", "目标二位于第五个位置。", 1000, 128,
            ("1 3\n3\n", "7 2\n6 7 9 1 2 3 5\n", "5 4\n4 5 7 9 2\n", "6 8\n1 3 5 7 9 11\n", f"20000 19999\n{' '.join(map(str, list(range(10000,20000))+list(range(10000))))}\n", "2 1\n2 1\n")),
        ProblemSpec("island-count", "四向岛屿计数", "medium", ("bfs", "matrix"),
            "在零一网格中，四个方向相邻的陆地格属于同一岛屿，统计岛屿数量。",
            "第一行 `n m`，随后 `n` 行长度为 `m` 的零一字符串。", "输出岛屿数量。",
            "`1 <= n,m <= 500`，`n*m <= 250000`。",
            _grid_case(["11000","11010","00100","00011"]), "左上角、中央单格、右侧单格和右下角分别形成四座岛屿。", 1800, 256,
            (_grid_case(["0"]), _grid_case(["11000","11010","00100","00011"]), _grid_case(["111","111","111"]), _grid_case(["10101","01010","10101"]), _grid_case([("10"*200)[:400] for _ in range(400)]), _grid_case(["10","01"]))),
        ProblemSpec("maze-shortest-steps", "迷宫最短步数", "medium", ("bfs", "shortest-path"),
            "在带障碍的网格中，从 S 出发每步上下左右移动一格，求到 T 的最少步数；不可达输出 -1。",
            "第一行 `n m`，随后为只含 `. # S T` 的网格，S 与 T 各一次。", "输出最少步数或 `-1`。",
            "`1 <= n,m <= 500`，`n*m <= 250000`。",
            _grid_case(["S..#",".#..","...T"]), "沿可通行格移动，最短路线需要五步。", 1800, 256,
            (_grid_case(["ST"]), _grid_case(["S..#",".#..","...T"]), _grid_case(["S...","....","...T"]), _grid_case(["S#.","###",".#T"]), _grid_case(["S"+"."*398,"."*399,"."*398+"T"]), _grid_case(["S#T","..."]))),
        ProblemSpec("graph-component-count", "无向图连通块", "medium", ("dfs", "graph-connectivity"),
            "统计无向图中的连通分量数量，孤立顶点也构成一个分量。",
            "第一行 `n m`，随后 `m` 行无向边 `u v`。", "输出连通分量数量。",
            "`1 <= n <= 200000`，`0 <= m <= 300000`，无自环，允许重边。",
            "6 3\n1 2\n2 3\n5 6\n", "顶点 1,2,3；顶点 4；顶点 5,6 共三个分量。", 1800, 256,
            ("1 0\n", "6 3\n1 2\n2 3\n5 6\n", "3 4\n1 2\n1 2\n2 3\n2 3\n", "6 0\n", "20000 19999\n"+"\n".join(f"{i} {i+1}" for i in range(1,20000))+"\n", "4 2\n1 2\n3 4\n")),
        ProblemSpec("union-find-queries", "动态连通查询", "medium", ("union-find", "graph-connectivity"),
            "初始有 n 个互不连通的点，在线处理合并操作和连通性询问。",
            "第一行 `n q`，随后操作为 `U a b` 或 `Q a b`。", "每个询问输出 `YES` 或 `NO`。",
            "`1 <= n,q <= 200000`，点编号 1 到 n。",
            "5 6\nQ 1 2\nU 1 2\nU 2 3\nQ 1 3\nQ 1 4\nQ 2 2\n", "合并后 1,2,3 连通；4 仍独立；任意点与自身连通。", 1800, 256,
            ("1 1\nQ 1 1\n", "5 6\nQ 1 2\nU 1 2\nU 2 3\nQ 1 3\nQ 1 4\nQ 2 2\n", "3 5\nU 1 2\nU 1 2\nQ 1 2\nU 2 1\nQ 2 3\n", "6 5\nU 1 2\nU 3 4\nU 5 6\nQ 2 4\nQ 5 6\n", "20000 20000\n"+"\n".join([f"U {i} {i+1}" for i in range(1,10001)]+[f"Q 1 {i}" for i in range(1,10001)])+"\n", "4 4\nU 1 2\nU 3 4\nQ 1 4\nQ 2 1\n")),
        ProblemSpec("directed-shortest-paths", "单源有向最短路", "medium", ("shortest-path", "graph"),
            "给定非负权有向图，计算源点到所有顶点的最短距离；不可达点输出 -1。",
            "第一行 `n m s`，随后 `m` 行为 `u v w`。", "输出 n 个整数。",
            "`1 <= n <= 100000`，`0 <= m <= 200000`，`0 <= w <= 10^9`。",
            "5 6 1\n1 2 4\n1 3 2\n3 2 1\n2 4 5\n3 4 8\n4 5 3\n", "到 2 的最短路经过 3，最终距离为 3。", 2200, 256,
            ("1 0 1\n", "5 6 1\n1 2 4\n1 3 2\n3 2 1\n2 4 5\n3 4 8\n4 5 3\n", "3 4 1\n1 2 5\n1 2 2\n2 3 1\n1 3 9\n", "5 2 3\n3 4 0\n4 5 0\n", "20000 19999 1\n"+"\n".join(f"{i} {i+1} 1000000000" for i in range(1,20000))+"\n", "4 4 1\n1 2 10\n1 3 1\n3 2 1\n2 4 1\n")),
        ProblemSpec("minimum-spanning-network", "最省连接网络", "medium", ("minimum-spanning-tree", "union-find"),
            "选择若干无向边连接全部顶点，使总权值最小；若无法连通输出 -1。",
            "第一行 `n m`，随后 `m` 行 `u v w`。", "输出最小生成树总权或 `-1`。",
            "`1 <= n <= 100000`，`0 <= m <= 200000`，`0 <= w <= 10^9`。",
            "4 5\n1 2 3\n1 3 1\n2 3 2\n2 4 4\n3 4 5\n", "选权值一、二、四的三条边，总权七。", 2200, 256,
            ("1 0\n", "4 5\n1 2 3\n1 3 1\n2 3 2\n2 4 4\n3 4 5\n", "3 4\n1 2 1\n1 2 1\n2 3 2\n1 3 5\n", "4 2\n1 2 1\n3 4 1\n", "20000 19999\n"+"\n".join(f"{i} {i+1} 1000000000" for i in range(1,20000))+"\n", "3 3\n1 2 100\n1 3 2\n3 2 3\n")),
        ProblemSpec("maximum-compatible-events", "最多可参加活动", "medium", ("greedy", "interval"),
            "每个活动占用半开区间 `[start,end)`，同一时刻只能参加一个活动，求最多可完整参加多少个。",
            "第一行 `n`，随后每行 `start end`。", "输出最多活动数。",
            "`1 <= n <= 200000`，`0 <= start < end <= 10^9`。",
            "5\n1 4\n3 5\n0 6\n5 7\n7 8\n", "选择 1-4、5-7、7-8 共三个活动。", 1500, 256,
            ("1\n0 1\n", "5\n1 4\n3 5\n0 6\n5 7\n7 8\n", "5\n1 3\n1 3\n1 3\n3 5\n3 5\n", "4\n0 10\n1 2\n2 3\n3 4\n", "20000\n"+"\n".join(f"{i} {i+1}" for i in range(20000))+"\n", "3\n1 100\n2 3\n3 4\n")),
        ProblemSpec("zero-one-knapsack", "单次选择背包", "medium", ("zero-one-knapsack", "dynamic-programming"),
            "每件物品最多选一次，在容量限制内最大化总价值。",
            "第一行 `n C`，随后 `n` 行为重量和价值。", "输出最大总价值。",
            "`1 <= n <= 500`，`1 <= C <= 20000`，重量不超过 C，价值不超过 `10^9`。",
            "4 7\n2 6\n3 10\n4 12\n5 13\n", "选择重量三和四的物品，价值二十二。", 2200, 256,
            ("1 1\n1 5\n", "4 7\n2 6\n3 10\n4 12\n5 13\n", "4 4\n2 5\n2 5\n2 5\n2 5\n", "3 5\n6 100\n5 1\n4 9\n".replace("6 100\n", "5 100\n"), "300 20000\n"+"\n".join(f"{i%100+1} {i*7919%100000+1}" for i in range(300))+"\n", "2 2\n1 3\n1 3\n")),
        ProblemSpec("minimum-coin-count", "最少硬币数", "medium", ("dynamic-programming",),
            "硬币面额可以无限次使用，凑出目标金额所需硬币数最少是多少；无法凑出输出 -1。",
            "第一行 `n target`，第二行 n 个互不相同的正面额。", "输出最少硬币数或 `-1`。",
            "`1 <= n <= 100`，`0 <= target <= 100000`，面额不超过 `10^5`。",
            "3 11\n1 5 7\n", "五加五加一共三枚。", 6000, 256,
            ("1 0\n7\n", "3 11\n1 5 7\n", "4 8\n2 3 4 7\n", "2 7\n4 6\n", "100 100000\n"+" ".join(map(str, range(1,101)))+"\n", "3 6\n1 3 4\n")),
        ProblemSpec("longest-increasing-subsequence", "严格递增子序列", "hard", ("longest-increasing-subsequence", "binary-search", "dynamic-programming"),
            "求数组的最长严格递增子序列长度。子序列可删除任意元素，但不能改变剩余元素相对顺序。",
            "第一行 `n`，第二行 n 个整数。", "输出最长长度。",
            "`1 <= n <= 200000`，元素绝对值不超过 `10^9`。",
            "8\n10 9 2 5 3 7 101 18\n", "例如 2,3,7,18 是长度四的严格递增子序列。", 1800, 256,
            ("1\n5\n", "8\n10 9 2 5 3 7 101 18\n", "6\n4 4 4 4 4 4\n", "6\n6 5 4 3 2 1\n", _array_case(lis_stress), "5\n1 2 2 3 4\n")),
        ProblemSpec("string-edit-distance", "字符串编辑距离", "hard", ("edit-distance", "dynamic-programming", "string"),
            "每次可以插入、删除或替换一个字符，求把第一个字符串变为第二个字符串的最少操作次数。",
            "两行分别为字符串 a 和 b；字符串可以为空行。", "输出最少操作次数。",
            "`0 <= |a|,|b| <= 3000`，字符为小写英文字母。",
            "kitten\nsitting\n", "替换 k、替换 e、末尾插入 g，共三次。", 3000, 256,
            ("\n\n", "kitten\nsitting\n", "aaaaaa\naaaaaa\n", "abcdef\nfedcba\n", "a"*1200+"\n"+"b"*1200+"\n", "ab\nba\n")),
        ProblemSpec("weighted-grid-route", "加权网格最低代价", "hard", ("shortest-path", "matrix"),
            "从左上角到右下角，每步上下左右移动，进入每个格子都会支付该格权值；起点权值也计入，求最小总代价。",
            "第一行 `n m`，随后 n 行每行 m 个正整数。", "输出最小总代价。",
            "`1 <= n,m <= 500`，`n*m <= 250000`，权值不超过 `10^9`。",
            "3 3\n1 9 1\n1 2 1\n9 1 1\n", "路径 1,1,2,1,1 的总代价为六。", 3000, 512,
            ("1 1\n7\n", "3 3\n1 9 1\n1 2 1\n9 1 1\n", "3 3\n5 5 5\n5 5 5\n5 5 5\n", "4 4\n1 100 100 100\n1 1 1 100\n100 100 1 100\n100 100 1 1\n", _matrix_case(weighted_grid), "2 3\n1 100 1\n1 1 1\n")),
        ProblemSpec("exact-k-nonadjacent", "恰选非相邻元素", "hard", ("dynamic-programming", "array"),
            "从数组中恰好选择 k 个互不相邻的位置，使元素和最大。题目保证存在合法选择，元素可以为负。",
            "第一行 `n k`，第二行 n 个整数。", "输出最大元素和。",
            "`1 <= n <= 2000`，`1 <= k <= (n+1)/2`，`|a_i| <= 10^9`。",
            "6 2\n5 1 4 9 2 8\n", "选择九和八，位置不相邻，和为十七。", 2600, 256,
            ("1 1\n-5\n", "6 2\n5 1 4 9 2 8\n", "7 3\n4 4 4 4 4 4 4\n", "5 3\n1 100 1 100 1\n", "1200 500\n"+" ".join(str((i*7919)%2000000001-1000000000) for i in range(1200))+"\n", "3 1\n-5 -1 -3\n")),
        ProblemSpec("offline-edge-deletions", "离线删边连通性", "hard", ("union-find", "graph-connectivity"),
            "无向图执行若干删边与连通询问。每条边最多删除一次，删除发生后永久有效。输出每次询问的答案。",
            "第一行 `n m q`；随后 m 行边；再 q 行 `D i` 删除第 i 条边，或 `Q u v` 询问。", "每个询问输出 `YES` 或 `NO`。",
            "`1 <= n,m,q <= 200000`，无自环，删除操作不重复。",
            "4 4 5\n1 2\n2 3\n3 4\n1 4\nQ 1 3\nD 2\nQ 1 3\nD 4\nQ 1 3\n", "先连通；删第二条边后仍可绕行；再删第四条边后不连通。", 3000, 512,
            ("2 1 1\n1 2\nQ 1 2\n", "4 4 5\n1 2\n2 3\n3 4\n1 4\nQ 1 3\nD 2\nQ 1 3\nD 4\nQ 1 3\n", "3 3 4\n1 2\n1 2\n2 3\nD 1\nQ 1 3\nD 2\nQ 1 3\n", "5 2 4\n1 2\n4 5\nQ 1 3\nQ 4 5\nD 2\nQ 4 5\n", "20000 19999 20000\n"+"\n".join(f"{i} {i+1}" for i in range(1,20000))+"\n"+"\n".join([f"Q 1 {i}" for i in range(1,10001)]+[f"D {i}" for i in range(1,10001)])+"\n", "3 2 3\n1 2\n2 3\nD 2\nQ 1 3\nQ 1 2\n")),
        ProblemSpec("kth-pair-distance", "第 K 小数对距离", "hard", ("binary-search", "two-pointers", "sorting"),
            "所有下标对 i<j 的距离定义为绝对差，求这些距离从小到大排序后的第 k 个。",
            "第一行 `n k`，第二行 n 个整数。", "输出第 k 小距离。",
            "`2 <= n <= 200000`，`1 <= k <= n(n-1)/2`，元素绝对值不超过 `10^9`。",
            "4 4\n1 3 6 10\n", "六个距离为 2,3,4,5,7,9，第四小为五。", 2600, 256,
            ("2 1\n5 5\n", "4 4\n1 3 6 10\n", "5 7\n2 2 2 2 2\n", "5 3\n-10 -1 0 1 10\n", "30000 449985000\n"+" ".join(str(i*1000) for i in range(30000))+"\n", "3 2\n1 1 2\n")),
        ProblemSpec("minimum-cover-cost", "覆盖线段最低成本", "medium", ("dynamic-programming", "interval"),
            "要覆盖整数线段 `[0,L]`。购买区间 `[l,r]` 可使当前已连续覆盖到 x 时扩展到 r，前提是 l<=x<r。每个区间可买一次，求最低成本；无法覆盖输出 -1。",
            "第一行 `L m`，随后 m 行 `l r cost`。", "输出最低成本或 `-1`。",
            "`1 <= L <= 5000`，`1 <= m <= 20000`，`0 <= l < r <= L`，`1 <= cost <= 10^9`。",
            "10 4\n0 4 5\n3 7 4\n6 10 6\n0 10 20\n", "依次购买前三个区间花费十五，比直接覆盖的二十更低。", 3000, 512,
            ("1 1\n0 1 7\n", "10 4\n0 4 5\n3 7 4\n6 10 6\n0 10 20\n", "5 4\n0 3 4\n0 3 4\n2 5 4\n2 5 4\n", "6 2\n0 2 1\n3 6 1\n", "2000 6000\n"+"\n".join(f"{i%1999} {min(2000,i%1999+1+(i*37)%30)} {1+(i*97)%1000}" for i in range(6000))+"\n", "5 3\n0 5 100\n0 2 1\n2 5 1\n")),
    )


TAGS = {
    "basic-io": "基础输入输出", "math": "数学", "array": "数组", "string": "字符串",
    "hash-table": "哈希表", "two-pointers": "双指针", "sliding-window": "滑动窗口",
    "prefix-sum": "前缀和", "stack": "栈", "queue": "队列", "simulation": "模拟",
    "binary-search": "二分查找", "sorting": "排序", "interval": "区间处理", "matrix": "矩阵",
    "bfs": "BFS", "dfs": "DFS", "graph": "图论", "graph-connectivity": "图连通性",
    "union-find": "并查集", "shortest-path": "最短路", "minimum-spanning-tree": "最小生成树",
    "greedy": "贪心", "zero-one-knapsack": "0/1 背包", "dynamic-programming": "动态规划",
    "longest-increasing-subsequence": "最长递增子序列", "edit-distance": "编辑距离",
}

COLLECTIONS = (
    ("acm-starter", "ACM 入门", "从标准输入输出、线性结构到基础查找，建立 ACM 编程习惯。",
     ("a-plus-b", "array-total", "reverse-line", "frequency-queries", "sorted-pair-exists", "balanced-brackets", "queue-commands", "first-occurrence", "stable-score-sort", "matrix-diagonal-sum")),
    ("core-data-structures", "核心数据结构", "覆盖数组、哈希、栈、队列、窗口、区间、图与并查集。",
     ("array-total", "frequency-queries", "balanced-brackets", "queue-commands", "longest-unique-segment", "range-sum-queries", "merge-intervals", "graph-component-count", "union-find-queries", "offline-edge-deletions")),
    ("algorithm-advanced", "算法进阶", "循序训练二分、图算法、贪心与动态规划。",
     ("rotated-array-search", "maze-shortest-steps", "directed-shortest-paths", "minimum-spanning-network", "maximum-compatible-events", "zero-one-knapsack", "minimum-coin-count", "longest-increasing-subsequence", "string-edit-distance", "weighted-grid-route", "exact-k-nonadjacent", "kth-pair-distance", "minimum-cover-cost")),
)


def run_python(source: Path, stdin: bytes) -> bytes:
    completed = subprocess.run(
        [sys.executable, str(source)], input=stdin, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=20,
    )
    if completed.returncode:
        raise RuntimeError(f"reference solution failed: {source.name}: {completed.stderr.decode(errors='replace')}")
    return completed.stdout.replace(b"\r\n", b"\n").rstrip() + b"\n"


def write_catalog() -> None:
    specs = problem_specs()
    if len(specs) != 30 or len({item.slug for item in specs}) != 30:
        raise RuntimeError("catalog must contain exactly 30 unique problems")
    problem_dir = ROOT / "problems"
    data_dir = ROOT / "test-data"
    reference_dir = ROOT / "reference-solutions"
    for directory in (problem_dir, data_dir, reference_dir):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
    for spec in specs:
        if spec.slug not in PYTHON_SOLUTIONS or spec.slug not in CPP_SOLUTIONS:
            raise RuntimeError(f"missing reference solution: {spec.slug}")
        if len(spec.cases) != 6:
            raise RuntimeError(f"{spec.slug} must have six hidden cases")
        solution_dir = reference_dir / spec.slug
        solution_dir.mkdir()
        python_path = solution_dir / "solution.py"
        cpp_path = solution_dir / "solution.cpp"
        python_path.write_text(PYTHON_SOLUTIONS[spec.slug], encoding="utf-8")
        cpp_path.write_text(CPP_SOLUTIONS[spec.slug] + "\n", encoding="utf-8")
        case_dir = data_dir / spec.slug
        case_dir.mkdir()
        cases = []
        for index, ((scenario, chinese), score, stdin_text) in enumerate(zip(SCENARIOS, SCORES, spec.cases), 1):
            stdin = stdin_text.encode()
            stdout = run_python(python_path, stdin)
            (case_dir / f"{index:02d}.in").write_bytes(stdin)
            (case_dir / f"{index:02d}.out").write_bytes(stdout)
            cases.append({
                "sequence": index, "score": score,
                "scenario": scenario,
                "scenario_description": f"{chinese}：验证 {spec.title} 在该类输入下的正确性。",
                "input_file": f"{spec.slug}/{index:02d}.in",
                "output_file": f"{spec.slug}/{index:02d}.out",
            })
        sample_output = run_python(python_path, spec.sample_input.encode()).decode()
        document = {
            "slug": spec.slug, "title": spec.title,
            "description": spec.story, "difficulty": spec.difficulty,
            "tags": list(spec.tags), "input_description": spec.input_description,
            "output_description": spec.output_description, "data_constraints": spec.constraints,
            "sample_input": spec.sample_input, "sample_output": sample_output,
            "sample_explanation": spec.sample_explanation,
            "time_limit_ms": spec.time_limit_ms, "memory_limit_mb": spec.memory_limit_mb,
            "source": "CodeArena 原创题库", "publish": True,
            "reference_solutions": {
                "python": f"reference-solutions/{spec.slug}/solution.py",
                "cpp": f"reference-solutions/{spec.slug}/solution.cpp",
            },
            "test_set": {"version": 1, "checker_type": "exact", "cases": cases},
        }
        (problem_dir / f"{spec.slug}.yaml").write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=1000),
            encoding="utf-8",
        )
    (ROOT / "tags.yaml").write_text(yaml.safe_dump(
        {"tags": [{"slug": slug, "name": name} for slug, name in TAGS.items()]},
        allow_unicode=True, sort_keys=False), encoding="utf-8")
    (ROOT / "collections.yaml").write_text(yaml.safe_dump({"collections": [
        {"slug": slug, "title": title, "description": description,
         "company": "CodeArena", "is_public": True, "problems": list(problems)}
        for slug, title, description, problems in COLLECTIONS
    ]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    daily = [
        {"date": "today" if index == 0 else f"today+{index}", "problem": specs[index].slug}
        for index in range(14)
    ]
    (ROOT / "daily-challenges.yaml").write_text(yaml.safe_dump(
        {"daily_challenges": daily}, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    (ROOT / "manifest.yaml").write_text(yaml.safe_dump({
        "schema_version": 1, "timezone": "Asia/Shanghai", "tags": "tags.yaml",
        "problems": [f"problems/{item.slug}.yaml" for item in specs],
        "collections": "collections.yaml", "daily_challenges": "daily-challenges.yaml",
        "test_data_directory": "test-data",
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"generated {len(specs)} problems, {len(specs) * 6} hidden cases, 3 collections and 14 challenges")


if __name__ == "__main__":
    write_catalog()
