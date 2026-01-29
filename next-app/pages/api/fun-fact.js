// ==== Fun Fact Generator API ====
// Generates interesting fun facts about cities using Groq AI

const GROQ_API_KEY = process.env.GROQ_API_KEY;
const GROQ_MODEL = process.env.GROQ_MODEL || 'mixtral-8x7b-32768';

// Debug logging
console.log('Fun Fact API - GROQ_API_KEY exists:', !!GROQ_API_KEY);
console.log('Fun Fact API - GROQ_API_KEY length:', GROQ_API_KEY?.length || 0);
console.log('Fun Fact API - GROQ_MODEL:', GROQ_MODEL);

// Cache for fun facts (24 hours)
const funFactCache = new Map();
const CACHE_TTL = 24 * 60 * 60 * 1000; // 24 hours

async function fetchGroqModels() {
  const resp = await fetch('https://api.groq.com/openai/v1/models', {
    headers: { Authorization: `Bearer ${GROQ_API_KEY}` },
  });
  if (!resp.ok) throw new Error('Failed to fetch Groq models');
  const data = await resp.json();
  return data.data?.map(m => m.id) || [];
}

function pickPreferredModel(models) {
  const preferred = [
    'llama-3.3-70b-versatile',
    'llama-3.1-70b-versatile', 
    'llama-3.1-8b-instant',
    'mixtral-8x7b-32768',
  ];
  for (const m of preferred) if (models.includes(m)) return m;
  return models[0] || GROQ_MODEL;
}

async function getGroqModel() {
  const now = Date.now();
  if (_cachedModel && (now - _cachedModelTs) < MODEL_TTL_MS) {
    return _cachedModel;
  }
  const models = await fetchGroqModels();
  _cachedModel = pickPreferredModel(models);
  _cachedModelTs = now;
  return _cachedModel;
}

function buildFunFactPrompt(city) {
  return `You are a travel expert. Generate one fascinating, surprising, or little-known fun fact about ${city}. 

Requirements:
- Make it genuinely interesting and not commonly known
- Keep it concise (1-2 sentences max)
- Focus on unique history, culture, geography, or modern facts
- Avoid clichés about food or famous landmarks everyone knows
- Make travelers want to visit more

Examples of good facts:
- "Tokyo's Shibuya Crossing sees up to 3,000 people cross at once during peak times, making it the world's busiest pedestrian crossing."
- "Singapore is the only country in the world that's also a city-state, and it's illegal to chew gum there."

Generate a fun fact about ${city}:`;
}

async function generateFunFact(city) {
  // Clear cache for testing
  // Check cache first
  const cacheKey = city.toLowerCase().trim();
  const cached = funFactCache.get(cacheKey);
  if (cached && (Date.now() - cached.timestamp) < CACHE_TTL) {
    console.log('Returning cached fact for:', city);
    return cached.fact;
  }

  console.log('=== GENERATING NEW FUN FACT ===');
  console.log('Generating fun fact for:', city);
  console.log('GROQ_API_KEY exists:', !!GROQ_API_KEY);
  console.log('GROQ_API_KEY length:', GROQ_API_KEY?.length || 0);

  try {
    const model = await getGroqModel();
    const prompt = buildFunFactPrompt(city);
    
    console.log('Making Groq API call...');
    
    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${GROQ_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: model,
        messages: [
          {
            role: 'user',
            content: prompt
          }
        ],
        max_tokens: 100,
        temperature: 0.7,
      }),
    });

    console.log('Groq API response status:', response.status);
    console.log('Groq API response headers:', response.headers);

    if (!response.ok) {
      const errorText = await response.text();
      console.log('Groq API error response:', errorText);
      throw new Error(`Groq API error: ${response.status} - ${errorText}`);
    }

    const data = await response.json();
    console.log('Groq API response data:', data);
    
    const fact = data.choices?.[0]?.message?.content?.trim();
    
    if (fact) {
      // Cache the result
      funFactCache.set(cacheKey, {
        fact: fact,
        timestamp: Date.now()
      });
      return fact;
    }
    
    throw new Error('No fact generated');
  } catch (error) {
    console.error('Fun fact generation failed:', error);
    // Return a fallback fact
    return `${city} has many fascinating stories and secrets waiting to be discovered by curious travelers.`;
  }
}

export default async function handler(req, res) {
  console.log('=== FUN FACT API CALLED ===');
  console.log('Environment check - GROQ_API_KEY exists:', !!process.env.GROQ_API_KEY);
  console.log('Environment check - GROQ_API_KEY length:', process.env.GROQ_API_KEY?.length || 0);
  
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { city } = req.body;
    console.log('City requested:', city);
    
    if (!city || typeof city !== 'string') {
      return res.status(400).json({ error: 'City is required' });
    }

    const funFact = await generateFunFact(city);
    console.log('Generated fun fact:', funFact);
    
    res.status(200).json({
      city: city,
      funFact: funFact,
      cached: funFactCache.has(city.toLowerCase().trim())
    });
    
  } catch (error) {
    console.error('Fun fact API error:', error);
    res.status(500).json({ 
      error: 'Failed to generate fun fact',
      message: error.message 
    });
  }
}
