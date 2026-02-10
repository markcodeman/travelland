"""
Test to verify max_results configuration is set to 5 across all layers.
Based on Miller's Law - optimal working memory capacity (7±2 items).
"""

import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_semantic_search_max_results():
    """Test that semantic.search_and_reason uses max_results=5"""

    # Check the default max_results in semantic.py
    print("✓ Testing semantic.py max_results configuration...")

    # Look for max_results=5 in search_and_reason function
    with open(os.path.join(os.path.dirname(__file__), "../src/semantic.py"), "r") as f:
        content = f.read()
        if "max_results=5" in content:
            print("  ✓ semantic.py uses max_results=5")
            return True
        else:
            print("  ✗ semantic.py does not use max_results=5")
            return False


def test_configuration_consistency():
    """Test that all files use consistent max_results value"""
    print("✓ Testing configuration consistency...")

    files_to_check = ["../src/semantic.py"]
    uses_5 = True

    for filename in files_to_check:
        filepath = os.path.join(os.path.dirname(__file__), filename)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                content = f.read()
                if "max_results=5" in content or "max_results = 5" in content:
                    print(f"  ✓ {filename} uses max_results=5")
                elif "max_results=3" in content or "max_results = 3" in content:
                    print(f"  ✗ {filename} uses max_results=3 (should be 5)")
                    uses_5 = False

    return uses_5


if __name__ == "__main__":
    print("\n=== Testing Max Results Configuration (Expected: 5) ===\n")

    tests = [
        test_semantic_search_max_results(),
        test_configuration_consistency(),
    ]

    print("\n=== Test Results ===")
    if all(tests):
        print("✓ All tests passed! Configuration is correct (max_results=5)")
        sys.exit(0)
    else:
        print("✗ Some tests failed. Please check the configuration.")
        sys.exit(1)
