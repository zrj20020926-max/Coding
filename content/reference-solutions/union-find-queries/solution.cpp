#include <iostream>
#include <numeric>
#include <string>
#include <vector>
using namespace std;int main(){ios::sync_with_stdio(false);int n,q;cin>>n>>q;vector<int>p(n),s(n,1);iota(p.begin(),p.end(),0);auto find=[&](int x){while(p[x]!=x)x=p[x]=p[p[x]];return x;};while(q--){char op;int a,b;cin>>op>>a>>b;--a;--b;a=find(a);b=find(b);if(op=='U'){if(a!=b){if(s[a]<s[b])swap(a,b);p[b]=a;s[a]+=s[b];}}else cout<<(a==b?"YES\n":"NO\n");}}
