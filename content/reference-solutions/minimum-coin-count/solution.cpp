#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n,t;cin>>n>>t;vector<int>a(n),d(t+1,t+1);for(int&x:a)cin>>x;d[0]=0;for(int x=1;x<=t;++x)for(int c:a)if(c<=x)d[x]=min(d[x],d[x-c]+1);cout<<(d[t]>t?-1:d[t])<<'\n';}
