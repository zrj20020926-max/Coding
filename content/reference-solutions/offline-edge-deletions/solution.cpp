#include <algorithm>
#include <iostream>
#include <numeric>
#include <string>
#include <tuple>
#include <vector>
using namespace std;int main(){int n,m,q;cin>>n>>m>>q;vector<pair<int,int>>e(m);for(auto&[a,b]:e){cin>>a>>b;--a;--b;}vector<tuple<char,int,int>>o;vector<char>d(m);while(q--){char c;int a,b=-1;cin>>c>>a;--a;if(c=='Q'){cin>>b;--b;}else d[a]=1;o.push_back({c,a,b});}vector<int>p(n),s(n,1);iota(p.begin(),p.end(),0);auto f=[&](int x){while(p[x]!=x)x=p[x]=p[p[x]];return x;};auto u=[&](int a,int b){a=f(a);b=f(b);if(a==b)return;if(s[a]<s[b])swap(a,b);p[b]=a;s[a]+=s[b];};for(int i=0;i<m;++i)if(!d[i])u(e[i].first,e[i].second);vector<string>ans;for(auto it=o.rbegin();it!=o.rend();++it){auto[c,a,b]=*it;if(c=='D')u(e[a].first,e[a].second);else ans.push_back(f(a)==f(b)?"YES":"NO");}reverse(ans.begin(),ans.end());for(auto&s:ans)cout<<s<<'\n';}
