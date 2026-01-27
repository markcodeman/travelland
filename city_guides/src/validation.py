from city_guides.src.neighborhood_disambiguator import NeighborhoodDisambiguator

# Move validation functions here if needed, or keep as is for now

def validate_neighborhood(neighborhood, city):
    return NeighborhoodDisambiguator.validate_neighborhood(neighborhood, city)

# Added for refactoring to support modularity
