#!/bin/bash
# AGENTS.md Pre-Flight Check
# Run this before every coding session to enforce no-harcoding rules

echo "=== AGENTS.md ENFORCEMENT CHECK ==="
echo ""
echo "MANDATORY: Before code changes, verify:"
echo "1. Am I adding static data? (dictionaries, lists, mappings)"
echo "2. Can this be fetched from an API? (Wikipedia, DDGS, OSM)"
echo "3. If YES to both → REJECT and use dynamic approach"
echo ""
echo "Banned Patterns:"
echo "  - city_profiles = {'paris': ...}"
echo "  - category_map = {'museum': 'Art'}"
echo "  - Hardcoded cultural terms, landmarks, fallback lists"
echo ""
echo "Required: Extract DIRECTLY from APIs without mapping layers"
echo "===================================="
