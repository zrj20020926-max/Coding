#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n,k;cin>>n>>k;const long long N=-(1LL<<60);vector<long long>s(k+1,N),t(k+1,N),ns,nt;s[0]=0;while(n--){long long x;cin>>x;ns=s;nt.assign(k+1,N);for(int j=0;j<=k;++j)ns[j]=max(s[j],t[j]);for(int j=1;j<=k;++j)if(s[j-1]>N)nt[j]=s[j-1]+x;s.swap(ns);t.swap(nt);}cout<<max(s[k],t[k])<<'\n';}
