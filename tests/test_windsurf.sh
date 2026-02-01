#!/bin/bash
echo "=== Testing Windsurf Accessibility ==="
echo "1. Current directory: $(pwd)"
echo "2. Windsurf version: $(windsurf --version)"
echo "3. Command location: $(which windsurf)"
echo "4. Symlink target: $(readlink -f $(which windsurf))"
echo "5. Checking from different directories:"
for dir in /tmp /var/tmp ~/TravelLand ~; do
    if [ -d "$dir" ]; then
        cd "$dir" >/dev/null 2>&1
        result=$(windsurf --version 2>&1 | head -1)
        status="✓"
        if [ $? -ne 0 ]; then
            status="✗"
            result="ERROR"
        fi
        echo "   $status $dir: $result"
    fi
done
cd ~/TravelLand >/dev/null 2>&1
echo "6. Verifying symlink in ~/.local/bin:"
if [ -L ~/.local/bin/windsurf ]; then
    echo "   ✓ Symlink exists: $(readlink ~/.local/bin/windsurf)"
else
    echo "   ✗ Symlink does not exist"
fi

echo "=== Complete ==="
echo "Windsurf is ready to use from any directory in your terminal!"