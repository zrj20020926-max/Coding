#include <iostream>
#include <queue>
#include <string>
#include <vector>
using namespace std;int main(){int n,m;cin>>n>>m;vector<string>g(n);for(auto&s:g)cin>>s;int ans=0,dx[4]={1,-1,0,0},dy[4]={0,0,1,-1};for(int i=0;i<n;++i)for(int j=0;j<m;++j)if(g[i][j]=='1'){++ans;queue<pair<int,int>>q;q.push({i,j});g[i][j]='0';while(!q.empty()){auto[x,y]=q.front();q.pop();for(int k=0;k<4;++k){int a=x+dx[k],b=y+dy[k];if(a>=0&&a<n&&b>=0&&b<m&&g[a][b]=='1'){g[a][b]='0';q.push({a,b});}}}}cout<<ans<<'\n';}
