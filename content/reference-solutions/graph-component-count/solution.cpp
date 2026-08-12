#include <iostream>
#include <vector>
using namespace std;int main(){int n,m;cin>>n>>m;vector<vector<int>>g(n);while(m--){int u,v;cin>>u>>v;--u;--v;g[u].push_back(v);g[v].push_back(u);}vector<char>seen(n);int ans=0;for(int r=0;r<n;++r)if(!seen[r]){++ans;vector<int>s={r};seen[r]=1;while(!s.empty()){int u=s.back();s.pop_back();for(int v:g[u])if(!seen[v])seen[v]=1,s.push_back(v);}}cout<<ans<<'\n';}
