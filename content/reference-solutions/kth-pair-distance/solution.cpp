#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n;long long k;cin>>n>>k;vector<long long>a(n);for(auto&x:a)cin>>x;sort(a.begin(),a.end());auto count=[&](long long d){long long z=0;int l=0;for(int r=0;r<n;++r){while(a[r]-a[l]>d)++l;z+=r-l;}return z;};long long l=0,r=a.back()-a.front();while(l<r){long long m=(l+r)/2;if(count(m)>=k)r=m;else l=m+1;}cout<<l<<'\n';}
