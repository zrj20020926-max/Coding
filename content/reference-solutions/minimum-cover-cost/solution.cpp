#include <algorithm>
#include <iostream>
#include <tuple>
#include <vector>
using namespace std;int main(){int L,m;cin>>L>>m;vector<tuple<int,int,long long>>a(m);for(auto&[l,r,c]:a)cin>>l>>r>>c;const long long I=4e18;vector<long long>d(L+1,I);d[0]=0;for(int x=0;x<L;++x)if(d[x]<I)for(auto[l,r,c]:a)if(l<=x&&x<r)d[min(L,r)]=min(d[min(L,r)],d[x]+c);cout<<(d[L]==I?-1:d[L])<<'\n';}
