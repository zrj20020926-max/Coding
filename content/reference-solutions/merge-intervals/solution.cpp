#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n;cin>>n;vector<pair<long long,long long>>a(n),b;for(auto&x:a)cin>>x.first>>x.second;sort(a.begin(),a.end());for(auto x:a)if(b.empty()||x.first>b.back().second)b.push_back(x);else b.back().second=max(b.back().second,x.second);cout<<b.size()<<'\n';for(auto x:b)cout<<x.first<<' '<<x.second<<'\n';}
