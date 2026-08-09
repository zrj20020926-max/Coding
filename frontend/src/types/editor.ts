export interface JudgeLanguage {
  id: number
  slug: string
  display_name: string
  version: string
  monaco_language: string
  source_filename: string
  sort_order: number
}

export const DEFAULT_CODE_TEMPLATES: Readonly<Record<string, string>> = {
  python: `import sys


def solve() -> None:
    data = sys.stdin.buffer.read().split()
    # Write your solution here.


if __name__ == "__main__":
    solve()
`,
  cpp: `#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    // Write your solution here.
    return 0;
}
`,
}

export function defaultCodeFor(language: string): string {
  return DEFAULT_CODE_TEMPLATES[language] ?? ''
}
