#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n;cin>>n;vector<long long>t;while(n--){long long x;cin>>x;auto it=lower_bound(t.begin(),t.end(),x);if(it==t.end())t.push_back(x);else*it=x;}cout<<t.size()<<'\n';}
