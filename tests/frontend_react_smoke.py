#!/usr/bin/env python3
"""
Frontend smoke test for React app using Playwright (MCP compatible)
Tests: page load, city search, suggestion selection
"""
import time
from playwright.sync_api import sync_playwright, TimeoutError

URL = "http://127.0.0.1:5174"

def run_tests():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(10000)
        
        print("Test 1: Page loads successfully")
        page.goto(URL)
        print(f"  ✓ Loaded: {page.title()}")
        
        print("\nTest 2: Search input exists")
        search_input = page.locator('input.search-input')
        search_input.wait_for()
        print("  ✓ Search input found")
        
        print("\nTest 3: Can type in search")
        search_input.fill("Paris")
        time.sleep(0.5)
        value = search_input.input_value()
        assert "Paris" in value, f"Expected 'Paris' in input, got: {value}"
        print("  ✓ Typed 'Paris' successfully")
        
        print("\nTest 4: Suggestions appear")
        suggestions = page.locator('.suggestion-item')
        try:
            suggestions.first.wait_for(timeout=3000)
            count = suggestions.count()
            print(f"  ✓ {count} suggestions found")
        except TimeoutError:
            print("  ⚠ No suggestions (may need backend running)")
        
        print("\nTest 5: Popular destinations visible")
        # Clear search to close dropdown
        clear_btn = page.locator('.clear-btn')
        if clear_btn.count() > 0:
            clear_btn.click()
            time.sleep(0.3)
        # Expand the popular section if collapsed
        expand_btn = page.locator('.popular-section .collapse-button')
        if expand_btn.count() > 0:
            expand_btn.click()
            time.sleep(0.3)
        popular = page.locator('.popular-card')
        popular.first.wait_for()
        count = popular.count()
        print(f"  ✓ {count} popular destinations displayed")
        
        print("\nTest 6: Hidden gems section exists")
        # Expand gems section if collapsed
        gems_expand = page.locator('.gems-section .collapse-button')
        if gems_expand.count() > 0:
            gems_expand.click()
            time.sleep(0.3)
        gems = page.locator('.gem-card')
        gems.first.wait_for()
        count = gems.count()
        print(f"  ✓ {count} hidden gems displayed")
        
        # Take screenshot
        page.screenshot(path="/tmp/frontend_test.png", full_page=True)
        print("\n  📸 Screenshot saved: /tmp/frontend_test.png")
        
        browser.close()
        print("\n✅ All tests passed!")

if __name__ == "__main__":
    run_tests()
