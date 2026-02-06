"""
Seeded Facts Loader - AGENTS.md compliant seed data access
Follows Controlled Seed Data principles with proper fallback logging
"""

import json
import logging
from pathlib import Path

# Configure logging for seed data usage
logger = logging.getLogger(__name__)

class SeededFacts:
    def __init__(self):
        self._seed_data = None
        self._seed_file = Path(__file__).resolve().parent.parent.parent.parent / "city_guides" / "data" / "seeded_cities.json"
        self._load_seed_data()
    
    def _load_seed_data(self):
        """Load seed data from JSON file"""
        try:
            if self._seed_file.exists():
                with open(self._seed_file, 'r') as f:
                    self._seed_data = json.load(f)
                logger.info(f"Loaded seed data: {self._seed_data.get('source', 'unknown')} v{self._seed_data.get('version', 'unknown')}")
            else:
                logger.warning(f"Seed file not found: {self._seed_file}")
                self._seed_data = {'cities': {}}
        except Exception as e:
            logger.error(f"Failed to load seed data: {e}")
            self._seed_data = {'cities': {}}
    
    def get_city_facts(self, city: str) -> list:
        """Get fun facts for a specific city from seed data"""
        if not self._seed_data:
            logger.warning("No seed data available")
            return []
        
        city_lower = city.lower().strip()
        facts = self._seed_data.get('cities', {}).get(city_lower, [])
        
        if facts:
            logger.info(f"Using seed data for {city}: {len(facts)} facts")
        else:
            logger.info(f"No seed data available for {city}")
        
        return facts
    
    def get_all_cities(self) -> list:
        """Get all cities available in seed data"""
        if not self._seed_data:
            return []
        return list(self._seed_data.get('cities', {}).keys())
    
    def get_metadata(self) -> dict:
        """Get seed data metadata"""
        if not self._seed_data:
            return {}
        return {
            'source': self._seed_data.get('source'),
            'version': self._seed_data.get('version'),
            'last_updated': self._seed_data.get('last_updated'),
            'refresh_strategy': self._seed_data.get('refresh_strategy'),
            'description': self._seed_data.get('description')
        }

# Global instance
seeded_facts = SeededFacts()

def get_city_fun_facts(city: str) -> list:
    """Get fun facts for a specific city (backward compatibility)"""
    return seeded_facts.get_city_facts(city)

def get_all_seeded_cities() -> list:
    """Get all cities with seed data"""
    return seeded_facts.get_all_cities()

def get_seed_metadata() -> dict:
    """Get seed data metadata"""
    return seeded_facts.get_metadata()
