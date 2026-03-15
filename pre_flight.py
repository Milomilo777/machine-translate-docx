import re

with open('src/machine-translate-docx.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Let's find all occurrences of checking action
results = []
for m in re.finditer(r'action (not in|in|==|!=)\s*(\[.*?\]|[\'"].*?[\'\"])', content):
    line_no = content[:m.start()].count('\n') + 1
    results.append(f"Line {line_no}: {m.group(0)}")

for r in results:
    print(r)
