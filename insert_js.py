import sys

js_code = '''                    js_script = """
                    // Select DeepLs editable input area
                    var textarea = document.querySelector('d-textarea[data-testid="translator-source-input"] div[contenteditable="true"]');
                    if (textarea) {
                        textarea.textContent = arguments[0];
                        textarea.dispatchEvent(new InputEvent('input', { bubbles: true }));
                        textarea.dispatchEvent(new Event('change', { bubbles: true }));
                        textarea.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: ' ' }));
                    }
                    """
'''

with open('src/machine-translate-docx.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

lines.insert(2895, js_code)

with open('src/machine-translate-docx.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
