#include <iostream>
#include <unordered_map>
using namespace std; int main(){ios::sync_with_stdio(false);cin.tie(nullptr);int n,q;cin>>n>>q;unordered_map<long long,int> c;long long x;while(n--){cin>>x;++c[x];}while(q--){cin>>x;cout<<c[x]<<'\n';}}
