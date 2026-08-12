#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n;cin>>n;vector<pair<long long,long long>>a(n);for(auto&x:a)cin>>x.first>>x.second;sort(a.begin(),a.end(),[](auto&x,auto&y){return x.second!=y.second?x.second<y.second:x.first<y.first;});long long last=-(1LL<<60);int ans=0;for(auto[s,e]:a)if(s>=last){++ans;last=e;}cout<<ans<<'\n';}
