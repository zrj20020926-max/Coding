#include <algorithm>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>
using namespace std;int main(){string a,b;getline(cin,a);getline(cin,b);vector<int>p(b.size()+1),c;iota(p.begin(),p.end(),0);for(int i=1;i<=(int)a.size();++i){c.assign(b.size()+1,0);c[0]=i;for(int j=1;j<=(int)b.size();++j)c[j]=min({c[j-1]+1,p[j]+1,p[j-1]+(a[i-1]!=b[j-1])});p.swap(c);}cout<<p.back()<<'\n';}
