#include <functional>
#include <iostream>
#include <queue>
#include <tuple>
#include <vector>
using namespace std;int main(){int n,m;cin>>n>>m;vector<vector<int>>a(n,vector<int>(m));for(auto&r:a)for(int&x:r)cin>>x;const long long I=4e18;vector<vector<long long>>d(n,vector<long long>(m,I));priority_queue<tuple<long long,int,int>,vector<tuple<long long,int,int>>,greater<tuple<long long,int,int>>>q;d[0][0]=a[0][0];q.push({d[0][0],0,0});int dx[4]={1,-1,0,0},dy[4]={0,0,1,-1};while(!q.empty()){auto[z,x,y]=q.top();q.pop();if(z!=d[x][y])continue;for(int k=0;k<4;++k){int u=x+dx[k],v=y+dy[k];if(u>=0&&u<n&&v>=0&&v<m&&z+a[u][v]<d[u][v]){d[u][v]=z+a[u][v];q.push({d[u][v],u,v});}}}cout<<d[n-1][m-1]<<'\n';}
