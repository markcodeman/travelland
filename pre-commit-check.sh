#!/bin/bash
# pre-commit-check.sh - Run basic validation before committing

echo "🔍 Running pre-commit checks..."

# Check Python syntax
echo "📝 Checking Python syntax..."
find . -name "*.py" -not -path "./.venv*" -not -path "./node_modules*" | while read file; do
    if ! python -m py_compile "$file" 2>/dev/null; then
        echo "❌ Python syntax error in $file"
        exit 1
    fi
done
echo "✅ Python syntax OK"

# Check JavaScript syntax (if node is available)
if command -v node &> /dev/null; then
    echo "📜 Checking JavaScript syntax..."
    find . -name "*.js" -not -path "./node_modules*" | while read file; do
        if ! node -c "$file" 2>/dev/null; then
            echo "❌ JavaScript syntax error in $file"
            exit 1
        fi
    done
    echo "✅ JavaScript syntax OK"
else
    echo "⚠️  Node.js not found, skipping JS checks"
fi

# Test Flask app import
echo "🌶️  Testing Flask app import..."
cd city_guides
if python -c "import app; print('✅ Flask app imports successfully')" 2>/dev/null; then
    echo "✅ Flask app import OK"
else
    echo "❌ Flask app import failed"
    exit 1
fi
cd ..

# Check for obvious issues
echo "🔍 Checking for common issues..."
if grep -r "console.log" city_guides/static/ --include="*.js" | grep -v "DEBUG\|console.log.*error\|console.log.*warn"; then
    echo "⚠️  Found console.log statements (consider removing for production)"
fi

echo "🎉 All checks passed! Ready to commit."