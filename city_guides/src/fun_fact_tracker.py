#!/usr/bin/env python3
"""
Track fun fact quality and auto-suggest cities for hardcoding
"""
import json
import time
from pathlib import Path
from typing import Dict, List

# Quality indicators
GENERIC_PHRASES = [
    "explore", "discover what makes", "special", "interesting", "visit",
    "is a city", "is a town", "is a commune", "is a major city",
    "is the capital", "is located in", "is situated in"
]

# High-quality indicators
QUALITY_INDICATORS = [
    "year", "years", "oldest", "largest", "first", "only", "famous",
    "world", "bridge", "castle", "festival", "unesco", "built", "founded",
    "meters", "feet", "inhabitants", "residents", "population", "billion",
    "million", "thousand", "unique", "tallest", "busiest", "most"
]

class FunFactTracker:
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.tracker_file = self.data_dir / "fun_fact_quality.json"
        self.candidates_file = self.data_dir / "hardcode_candidates.json"
        
        self.load_data()
    
    def load_data(self):
        """Load existing tracking data"""
        try:
            with open(self.tracker_file, 'r') as f:
                self.quality_data = json.load(f)
        except FileNotFoundError:
            self.quality_data = {}
        
        try:
            with open(self.candidates_file, 'r') as f:
                self.candidates = json.load(f)
        except FileNotFoundError:
            self.candidates = []
    
    def save_data(self):
        """Save tracking data"""
        with open(self.tracker_file, 'w') as f:
            json.dump(self.quality_data, f, indent=2)
        
        with open(self.candidates_file, 'w') as f:
            json.dump(self.candidates, f, indent=2)
    
    def track_fact(self, city: str, fact: str, source: str = "unknown"):
        """Track a fun fact and its quality"""
        city_key = city.lower().strip()
        
        if city_key not in self.quality_data:
            self.quality_data[city_key] = {
                "attempts": 0,
                "facts": [],
                "sources": [],
                "quality_scores": [],
                "avg_quality": 0.0,
                "last_attempt": 0
            }
        
        # Calculate quality score
        score = self.calculate_quality_score(fact)
        
        # Record this attempt
        self.quality_data[city_key]["attempts"] += 1
        self.quality_data[city_key]["facts"].append(fact)
        self.quality_data[city_key]["sources"].append(source)
        self.quality_data[city_key]["quality_scores"].append(score)
        self.quality_data[city_key]["last_attempt"] = time.time()
        
        # Update average
        scores = self.quality_data[city_key]["quality_scores"]
        self.quality_data[city_key]["avg_quality"] = sum(scores) / len(scores)
        
        # Check if this city should be a hardcoding candidate
        self.check_candidate(city_key)
        
        self.save_data()
    
    def calculate_quality_score(self, fact: str) -> float:
        """Calculate quality score (0.0 = generic, 1.0 = excellent)"""
        fact_lower = fact.lower()
        
        # Start with base score
        score = 0.5
        
        # Penalize generic phrases heavily
        for phrase in GENERIC_PHRASES:
            if phrase in fact_lower:
                score -= 0.2
                if phrase in ["explore", "discover what makes"]:
                    score -= 0.3  # Extra penalty for the worst offenders
        
        # Reward quality indicators
        for indicator in QUALITY_INDICATORS:
            if indicator in fact_lower:
                score += 0.1
        
        # Specific bonuses
        if any(num in fact for num in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]):
            score += 0.2  # Numbers add credibility
        
        if len(fact) < 50 or len(fact) > 200:
            score -= 0.1  # Too short or too long
        
        # Clamp between 0 and 1
        return max(0.0, min(1.0, score))
    
    def check_candidate(self, city_key: str):
        """Check if city should be a hardcoding candidate"""
        data = self.quality_data[city_key]
        
        # Must have at least 3 attempts
        if data["attempts"] < 3:
            return
        
        # Average quality below 0.3 = poor quality
        if data["avg_quality"] < 0.3:
            # Check if already in candidates
            if not any(c["city"] == city_key for c in self.candidates):
                self.candidates.append({
                    "city": city_key,
                    "attempts": data["attempts"],
                    "avg_quality": data["avg_quality"],
                    "last_attempt": data["last_attempt"],
                    "sample_facts": data["facts"][-3:],  # Last 3 attempts
                    "priority": self.calculate_priority(data)
                })
                # Sort by priority
                self.candidates.sort(key=lambda x: x["priority"], reverse=True)
    
    def calculate_priority(self, data: Dict) -> float:
        """Calculate priority for hardcoding (higher = more urgent)"""
        # More attempts + lower quality = higher priority
        priority = data["attempts"] * (1.0 - data["avg_quality"])
        
        # Bonus for recent failures (more likely to be requested)
        time_since = time.time() - data["last_attempt"]
        if time_since < 86400 * 7:  # Within 7 days
            priority += 0.5
        
        return priority
    
    def get_top_candidates(self, limit: int = 10) -> List[Dict]:
        """Get top cities that need hardcoding"""
        return self.candidates[:limit]
    
    def generate_hardcode_template(self, city: str) -> str:
        """Generate a template for hardcoding a city"""
        city_key = city.lower().strip()
        if city_key not in self.quality_data:
            return f"# No data for {city}\n"
        
        data = self.quality_data[city_key]
        template = f"            '{city_key}': [\n"
        
        # Add the best fact as first entry
        if data["facts"]:
            best_idx = max(range(len(data["quality_scores"])), 
                          key=lambda i: data["quality_scores"][i])
            best_fact = data["facts"][best_idx]
            template += f'                "{best_fact}",\n'
        
        template += "                # TODO: Add more curated facts here\n"
        template += "            ],\n"
        
        return template
    
    def get_stats(self) -> Dict:
        """Get tracking statistics"""
        total_cities = len(self.quality_data)
        total_attempts = sum(d["attempts"] for d in self.quality_data.values())
        avg_quality = sum(d["avg_quality"] for d in self.quality_data.values()) / total_cities if total_cities > 0 else 0
        candidates_count = len(self.candidates)
        
        return {
            "total_cities_tracked": total_cities,
            "total_attempts": total_attempts,
            "average_quality": avg_quality,
            "hardcode_candidates": candidates_count,
            "quality_distribution": self.get_quality_distribution()
        }
    
    def get_quality_distribution(self) -> Dict[str, int]:
        """Get distribution of quality scores"""
        ranges = {
            "excellent (0.8-1.0)": 0,
            "good (0.6-0.8)": 0,
            "fair (0.4-0.6)": 0,
            "poor (0.2-0.4)": 0,
            "generic (0.0-0.2)": 0
        }
        
        for data in self.quality_data.values():
            avg = data["avg_quality"]
            if avg >= 0.8:
                ranges["excellent (0.8-1.0)"] += 1
            elif avg >= 0.6:
                ranges["good (0.6-0.8)"] += 1
            elif avg >= 0.4:
                ranges["fair (0.4-0.6)"] += 1
            elif avg >= 0.2:
                ranges["poor (0.2-0.4)"] += 1
            else:
                ranges["generic (0.0-0.2)"] += 1
        
        return ranges

# Global instance for use in app.py
tracker = None

def get_tracker() -> FunFactTracker:
    """Get or create the global tracker instance"""
    global tracker
    if tracker is None:
        tracker = FunFactTracker()
    return tracker

def track_fun_fact(city: str, fact: str, source: str = "unknown"):
    """Convenience function to track a fun fact"""
    get_tracker().track_fact(city, fact, source)
