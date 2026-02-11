#!/usr/bin/env python3
"""
CLI tool to review hardcode candidates and manage fun fact quality
"""
import json
import sys
from pathlib import Path
from city_guides.src.fun_fact_tracker import FunFactTracker

def show_stats():
    """Show tracking statistics"""
    tracker = FunFactTracker()
    stats = tracker.get_stats()
    
    print("\n📊 Fun Fact Quality Statistics")
    print("=" * 40)
    print(f"Total cities tracked: {stats['total_cities_tracked']}")
    print(f"Total attempts: {stats['total_attempts']}")
    print(f"Average quality: {stats['average_quality']:.2f}")
    print(f"Cities needing hardcoding: {stats['hardcode_candidates']}")
    
    print("\n📈 Quality Distribution:")
    for range_name, count in stats['quality_distribution'].items():
        bar = "█" * count
        print(f"  {range_name}: {count:2d} {bar}")

def show_candidates(limit=10):
    """Show top hardcode candidates"""
    tracker = FunFactTracker()
    candidates = tracker.get_top_candidates(limit)
    
    print(f"\n🎯 Top {limit} Hardcode Candidates")
    print("=" * 40)
    
    for i, candidate in enumerate(candidates, 1):
        city = candidate['city'].title()
        attempts = candidate['attempts']
        quality = candidate['avg_quality']
        priority = candidate['priority']
        
        print(f"\n{i}. {city}")
        print(f"   Attempts: {attempts} | Quality: {quality:.2f} | Priority: {priority:.2f}")
        print("   Recent facts:")
        for fact in candidate['sample_facts']:
            print(f"     - {fact[:80]}...")

def generate_templates(limit=5):
    """Generate hardcode templates for top candidates"""
    tracker = FunFactTracker()
    candidates = tracker.get_top_candidates(limit)
    
    print(f"\n📝 Hardcode Templates for Top {limit}")
    print("=" * 40)
    
    for candidate in candidates:
        city = candidate['city']
        template = tracker.generate_hardcode_template(city)
        print(f"\n{city.title()}:")
        print(template)

def export_candidates():
    """Export candidates to JSON for review"""
    tracker = FunFactTracker()
    candidates = tracker.get_top_candidates(50)
    
    output_file = Path("hardcode_candidates_export.json")
    with open(output_file, 'w') as f:
        json.dump(candidates, f, indent=2)
    
    print(f"\n✅ Exported {len(candidates)} candidates to {output_file}")

def main():
    """CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: python fun_fact_cli.py [stats|candidates|templates|export]")
        print("  stats     - Show quality statistics")
        print("  candidates - Show top hardcode candidates")
        print("  templates  - Generate hardcode templates")
        print("  export    - Export candidates to JSON")
        return
    
    command = sys.argv[1]
    
    if command == "stats":
        show_stats()
    elif command == "candidates":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        show_candidates(limit)
    elif command == "templates":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        generate_templates(limit)
    elif command == "export":
        export_candidates()
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
