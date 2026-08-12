#include <algorithm>
#include <iostream>
#include <numeric>
#include <vector>
using namespace std;struct E{int u,v,w;};int main(){int n,m;cin>>n>>m;vector<E>e(m);for(auto&x:e){cin>>x.u>>x.v>>x.w;--x.u;--x.v;}sort(e.begin(),e.end(),[](auto&a,auto&b){return a.w<b.w;});vector<int>p(n),s(n,1);iota(p.begin(),p.end(),0);auto f=[&](int x){while(p[x]!=x)x=p[x]=p[p[x]];return x;};long long ans=0;int used=0;for(auto x:e){int a=f(x.u),b=f(x.v);if(a!=b){if(s[a]<s[b])swap(a,b);p[b]=a;s[a]+=s[b];ans+=x.w;++used;}}cout<<(used==n-1?ans:-1)<<'\n';}
