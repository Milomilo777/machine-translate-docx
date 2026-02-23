with open('src/machine-translate-docx.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Replace the block around 2896
# lines are 0-indexed. 2896 is index 2895.
start_idx = 2895
# Need to find where it ends.
# I'll just rewrite the specific lines if I can pinpoint them.
# The previous sed might have failed or partially worked.
# Let's inspect the lines first.
for i in range(2890, 2905):
    print(f"{i+1}: {lines[i]}")
