import sys
s = sys.stdin.buffer.readline().strip().decode()
stack = []
pairs = {')': '(', ']': '[', '}': '{'}
for ch in s:
    if ch in "([{":
        stack.append(ch)
    elif not stack or stack.pop() != pairs[ch]:
        print("NO")
        break
else:
    print("YES" if not stack else "NO")
