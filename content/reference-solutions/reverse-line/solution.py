import sys
s = sys.stdin.buffer.readline().rstrip(b"\r\n").decode()
print(s[::-1])
