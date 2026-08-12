#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n;long long t;cin>>n>>t;vector<long long>a(n);for(auto&x:a)cin>>x;auto it=lower_bound(a.begin(),a.end(),t);cout<<(it!=a.end()&&*it==t?it-a.begin()+1:-1)<<'\n';}
