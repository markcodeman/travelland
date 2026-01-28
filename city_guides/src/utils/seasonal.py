# Seasonal logic utilities

from datetime import datetime

# Seasonal recommendations (current month)
def get_seasonal_destinations(month, hemisphere='northern'):
    """Get seasonal destinations based on month and hemisphere"""
    seasonal_destinations = {
        # Summer (June-August): Beach destinations
        6: {'barcelona': 2.0, 'rio de janeiro': 2.0, 'sydney': 2.0, 'lisbon': 2.0, 'amsterdam': 2.0},
        7: {'barcelona': 2.0, 'rio de janeiro': 2.0, 'sydney': 2.0, 'lisbon': 2.0, 'amsterdam': 2.0},
        8: {'barcelona': 2.0, 'rio de janeiro': 2.0, 'sydney': 2.0, 'lisbon': 2.0, 'amsterdam': 2.0},
        # Winter (December-February): Ski/cold destinations
        12: {'zurich': 2.0, 'vienna': 2.0, 'stockholm': 2.0, 'oslo': 2.0, 'helsinki': 2.0},
        1: {'zurich': 2.0, 'vienna': 2.0, 'stockholm': 2.0, 'oslo': 2.0, 'helsinki': 2.0},
        2: {'zurich': 2.0, 'vienna': 2.0, 'stockholm': 2.0, 'oslo': 2.0, 'helsinki': 2.0},
        # Spring (March-May): Cultural cities
        3: {'paris': 2.0, 'rome': 2.0, 'athens': 2.0, 'prague': 2.0, 'budapest': 2.0},
        4: {'paris': 2.0, 'rome': 2.0, 'athens': 2.0, 'prague': 2.0, 'budapest': 2.0},
        5: {'paris': 2.0, 'rome': 2.0, 'athens': 2.0, 'prague': 2.0, 'budapest': 2.0},
        # Fall (September-November): Food/wine destinations
        9: {'madrid': 2.0, 'rome': 2.0, 'paris': 2.0, 'lisbon': 2.0, 'barcelona': 2.0},
        10: {'madrid': 2.0, 'rome': 2.0, 'paris': 2.0, 'lisbon': 2.0, 'barcelona': 2.0},
        11: {'madrid': 2.0, 'rome': 2.0, 'paris': 2.0, 'lisbon': 2.0, 'barcelona': 2.0}
    }
    
    if hemisphere == 'southern':
        # Shift months by 6 months for opposite seasons
        month = ((month + 5) % 12) + 1
    
    return seasonal_destinations.get(month, {})
