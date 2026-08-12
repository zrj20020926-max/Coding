#include <algorithm>
#include <iostream>
#include <unordered_map>
using namespace std;int main(){int n;cin>>n;unordered_map<long long,int>last;int l=0,ans=0;for(int r=0;r<n;++r){long long x;cin>>x;if(last.count(x))l=max(l,last[x]+1);last[x]=r;ans=max(ans,r-l+1);}cout<<ans<<'\n';}
