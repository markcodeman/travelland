import { useEffect, useState } from 'react';
import './FunFact.css';

const NeighborhoodFunFact = ({ city, neighborhood }) => {
  const [funFact, setFunFact] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Neighborhood-specific fun facts
  const neighborhoodFacts = {
    'shibuya': [
      "Shibuya Crossing is the world's busiest pedestrian crossing with up to 3,000 people crossing at once!",
      "The Hachiko statue at Shibuya Station is a famous meeting spot honoring a loyal dog who waited for his owner for 10 years.",
      "Shibuya 109 is a legendary fashion mall that launched many Japanese fashion trends."
    ],
    'shinjuku': [
      "Shinjuku Station is the world's busiest railway station, used by over 3.5 million passengers daily.",
      "Shinjuku Gyoen National Garden has three different garden styles: English Landscape, French Formal, and Japanese Traditional.",
      "The Tokyo Metropolitan Government Building in Shinjuku offers free observation decks with panoramic city views."
    ],
    'ginza': [
      "Ginza is one of the world's most expensive shopping districts, with land prices exceeding $100,000 per square meter.",
      "The Wako Department Store in Ginza is famous for its clock tower and has been a landmark since 1932.",
      "Ginza's Chuo Dori street becomes a pedestrian paradise on weekend afternoons."
    ],
    'harajuku': [
      "Takeshita Street in Harajuku is the epicenter of Japanese youth culture and street fashion.",
      "Meiji Jingu Shrine near Harajuku is dedicated to Emperor Meiji and Empress Shoken, surrounded by a dense forest.",
      "Harajuku's crepe shops have been serving sweet treats to fashion-conscious youth since the 1970s."
    ],
    'akihabara': [
      "Akihabara is known as 'Electric Town' with over 1,000 electronics and anime shops.",
      "The Radio Kaikan building in Akihabara is a mecca for anime and manga fans.",
      "Akihabara's maid cafes originated here and have become a cultural phenomenon."
    ],
    'ueno': [
      "Ueno Park is home to several museums, including the Tokyo National Museum, the oldest museum in Japan.",
      "Ueno Zoo is Japan's oldest zoo, founded in 1882 and famous for its pandas.",
      "The Ueno Toshogu Shrine is a beautiful ornate shrine dedicated to Tokugawa Ieyasu."
    ],
    'tamachi': [
      "Tamachi means 'town within the castle' and was historically part of the Edo Castle grounds.",
      "Tamachi Station is one of Tokyo's major railway hubs on the Yamanote Line.",
      "The area is known for its concentration of corporate headquarters and business hotels."
    ],
    'roppongi': [
      "Roppongi Hills is a massive complex with 239 meters tall Mori Tower offering panoramic Tokyo views.",
      "The area was named after the 'six trees' (roppongi) that once marked the boundaries.",
      "Roppongi is famous for its nightlife and has been an entertainment district since the 1960s."
    ],
    'ikebukuro': [
      "Ikebukuro Station is the second busiest railway station in Japan after Shinjuku.",
      "Sunshine City in Ikebukuro was once Tokyo's tallest building and has an aquarium on the top floor.",
      "The area is famous for its anime shops and Otome Road, a street targeting female anime fans."
    ],
    'asakusa': [
      "Sensoji Temple in Asakusa is Tokyo's oldest temple, founded in 645 AD.",
      "Nakamise-dori leading to Sensoji Temple has been selling traditional goods for centuries.",
      "Asakusa's Tokyo Skytree is the world's second tallest tower at 634 meters."
    ]
  };

  useEffect(() => {
    if (!city || !neighborhood) return;

    const getNeighborhoodFact = () => {
      setLoading(true);
      setError(null);
      
      try {
        const neighborhoodKey = neighborhood.toLowerCase();
        const facts = neighborhoodFacts[neighborhoodKey];
        
        if (facts && facts.length > 0) {
          // Randomly select a fact for this neighborhood
          const randomFact = facts[Math.floor(Math.random() * facts.length)];
          setFunFact(randomFact);
        } else {
          // Fallback to city fact if no neighborhood-specific fact
          setFunFact(`${neighborhood} is a vibrant neighborhood in ${city} with unique local character.`);
        }
      } catch (err) {
        setError('Could not load neighborhood fun fact');
        console.error('Error loading neighborhood fun fact:', err);
      } finally {
        setLoading(false);
      }
    };

    getNeighborhoodFact();
  }, [city, neighborhood]);

  if (loading) {
    return (
      <div className="fun-fact fun-fact--loading">
        <div className="loading-pill" />
        <div className="loading-line loading-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="fun-fact fun-fact--error">
        <p>Could not load fun fact</p>
      </div>
    );
  }

  if (!funFact) {
    return null;
  }

  return (
    <div className="fun-fact">
      <div className="fun-fact-content">
        <div className="fun-fact-icon">💡</div>
        <div className="fun-fact-text">
          <h3>FUN FACT about {neighborhood.toUpperCase()}</h3>
          <p>{funFact}</p>
        </div>
      </div>
    </div>
  );
};

export default NeighborhoodFunFact;
