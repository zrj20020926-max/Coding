#include <iostream>
#include <queue>
#include <string>
#include <vector>
using namespace std;int main(){int n,m;cin>>n>>m;vector<string>g(n);pair<int,int>s,t;for(int i=0;i<n;++i){cin>>g[i];for(int j=0;j<m;++j){if(g[i][j]=='S')s={i,j};if(g[i][j]=='T')t={i,j};}}vector<vector<int>>d(n,vector<int>(m,-1));queue<pair<int,int>>q;q.push(s);d[s.first][s.second]=0;int dx[4]={1,-1,0,0},dy[4]={0,0,1,-1};while(!q.empty()){auto[x,y]=q.front();q.pop();for(int k=0;k<4;++k){int a=x+dx[k],b=y+dy[k];if(a>=0&&a<n&&b>=0&&b<m&&g[a][b]!='#'&&d[a][b]<0){d[a][b]=d[x][y]+1;q.push({a,b});}}}cout<<d[t.first][t.second]<<'\n';}
