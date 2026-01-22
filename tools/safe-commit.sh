#!/bin/bash
# safe-commit.sh - Safely commit changes with validation

echo "🔒 Safe Commit Workflow"
echo "======================"

# Check if there are changes
if git diff --quiet && git diff --staged --quiet; then
    echo "ℹ️  No changes to commit"
    exit 0
fi

echo "📋 Current changes:"
git status --short

echo ""
echo "🔍 Running pre-commit checks..."
if ./pre-commit-check.sh; then
    echo ""
    echo "✅ Checks passed! Ready to commit."
    echo ""

    # Get commit message
    if [ -z "$1" ]; then
        echo "Enter commit message:"
        read -r message
    else
        message="$*"
    fi

    # Commit
    git add -A
    git commit -m "$message"

    echo ""
    echo "🎉 Successfully committed!"
    echo "   Message: $message"
else
    echo ""
    echo "❌ Pre-commit checks failed. Please fix issues before committing."
    exit 1
fi