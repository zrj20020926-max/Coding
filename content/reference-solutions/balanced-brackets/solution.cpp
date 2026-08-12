#include <iostream>
#include <stack>
#include <string>
using namespace std; int main(){string s,t;cin>>s;for(char c:s){if(c=='('||c=='['||c=='{')t+=c;else{char need=c==')'?'(':c==']'?'[':'{';if(t.empty()||t.back()!=need){cout<<"NO\n";return 0;}t.pop_back();}}cout<<(t.empty()?"YES\n":"NO\n");}
