#!/usr/bin/env python3
"""
Extract and lint JavaScript from Python files containing embedded JS.
Specifically designed for city_guides/src/routes/admin.py
"""
import re
import sys
import subprocess
import tempfile
import os

def extract_js_from_python(python_file: str) -> str | None:
    """Extract JavaScript from <script> tags in a Python file."""
    with open(python_file, 'r') as f:
        content = f.read()
    
    # Look for <script>...</script> pattern
    match = re.search(r'<script>(.*?)</script>', content, re.DOTALL)
    if match:
        return match.group(1)
    return None

def lint_js(js_code: str) -> bool:
    """Lint extracted JavaScript using Node.js --check."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(js_code)
        temp_path = f.name
    
    try:
        result = subprocess.run(
            ['node', '--check', temp_path],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"✗ JavaScript syntax error:\n{result.stderr}")
            return False
        return True
    finally:
        os.unlink(temp_path)

def main():
    python_file = sys.argv[1] if len(sys.argv) > 1 else 'city_guides/src/routes/admin.py'
    
    print(f"Extracting JavaScript from {python_file}...")
    js_code = extract_js_from_python(python_file)
    
    if not js_code:
        print("✗ No JavaScript found in <script> tags")
        sys.exit(1)
    
    print(f"Extracted {len(js_code)} characters of JavaScript")
    
    if lint_js(js_code):
        print("✓ JavaScript syntax is valid")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
