#include <algorithm>
#include <iostream>
#include <string>
#include <vector>
using namespace std;struct R{string n;int s,i;};int main(){int n;cin>>n;vector<R>a(n);for(int i=0;i<n;++i){cin>>a[i].n>>a[i].s;a[i].i=i;}stable_sort(a.begin(),a.end(),[](auto&x,auto&y){return x.s>y.s;});for(auto&r:a)cout<<r.n<<' '<<r.s<<'\n';}
