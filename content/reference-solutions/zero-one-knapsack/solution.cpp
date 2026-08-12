#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;int main(){int n,c;cin>>n>>c;vector<long long>d(c+1);while(n--){int w,v;cin>>w>>v;for(int x=c;x>=w;--x)d[x]=max(d[x],d[x-w]+v);}cout<<d[c]<<'\n';}
