#include <iostream>
#include <vector>
using namespace std; int main(){int n;long long t;cin>>n>>t;vector<long long>a(n);for(auto&x:a)cin>>x;int l=0,r=n-1;while(l<r){auto s=a[l]+a[r];if(s==t){cout<<"YES\n";return 0;}s<t?++l:--r;}cout<<"NO\n";}
