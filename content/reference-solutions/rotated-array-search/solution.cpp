#include <iostream>
#include <vector>
using namespace std;int main(){int n;long long t;cin>>n>>t;vector<long long>a(n);for(auto&x:a)cin>>x;int l=0,r=n-1;while(l<=r){int m=(l+r)/2;if(a[m]==t){cout<<m+1<<'\n';return 0;}if(a[l]<=a[m]){if(a[l]<=t&&t<a[m])r=m-1;else l=m+1;}else{if(a[m]<t&&t<=a[r])l=m+1;else r=m-1;}}cout<<-1<<'\n';}
