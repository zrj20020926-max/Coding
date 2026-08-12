#include <iostream>
#include <queue>
#include <string>
using namespace std; int main(){ios::sync_with_stdio(false);int q;cin>>q;queue<long long>a;while(q--){string op;cin>>op;if(op=="push"){long long x;cin>>x;a.push(x);}else if(op=="pop"){if(a.empty())cout<<"EMPTY\n";else{cout<<a.front()<<'\n';a.pop();}}else if(op=="front")cout<<(a.empty()?"EMPTY":to_string(a.front()))<<'\n';else cout<<a.size()<<'\n';}}
