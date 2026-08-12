#include <functional>
#include <iostream>
#include <queue>
#include <vector>
using namespace std;int main(){int n,m,s;cin>>n>>m>>s;--s;vector<vector<pair<int,int>>>g(n);while(m--){int u,v,w;cin>>u>>v>>w;g[--u].push_back({--v,w});}const long long I=4e18;vector<long long>d(n,I);priority_queue<pair<long long,int>,vector<pair<long long,int>>,greater<pair<long long,int>>>q;d[s]=0;q.push({0,s});while(!q.empty()){auto[x,u]=q.top();q.pop();if(x!=d[u])continue;for(auto[v,w]:g[u])if(x+w<d[v]){d[v]=x+w;q.push({d[v],v});}}for(int i=0;i<n;++i)cout<<(d[i]==I?-1:d[i])<<(i+1==n?'\n':' ');}
