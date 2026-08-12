#include <iostream>
#include <vector>
using namespace std;int main(){ios::sync_with_stdio(false);cin.tie(nullptr);int n,q;cin>>n>>q;vector<long long>p(n+1);for(int i=1;i<=n;++i){cin>>p[i];p[i]+=p[i-1];}while(q--){int l,r;cin>>l>>r;cout<<p[r]-p[l-1]<<'\n';}}
