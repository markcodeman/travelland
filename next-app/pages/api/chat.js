// ==== Load Groq configuration ====
const GROQ_API_KEY = process.env.GROQ_API_KEY;
const GROQ_MODEL = process.env.GROQ_MODEL || 'llama-3.3-70b-versatile';

// ==== Request tracking per session (1 request per session limit) ====
const sessionRequestCounts = new Map();
const MAX_REQUESTS_PER_SESSION = 1;

// Evergreen Groq model resolver (caches for 10m)
let _cachedModel = null;
let _cachedModelTs = 0;
const MODEL_TTL_MS = 10 * 60 * 1000;

async function fetchGroqModels() {
  const resp = await fetch('https://api.groq.com/openai/v1/models', {
    headers: { Authorization: `Bearer ${GROQ_API_KEY}` },
  });
  if (!resp.ok) throw new Error('Failed to fetch Groq models');
  const data = await resp.json();
  return data.data?.map(m => m.id) || [];
}

function pickPreferredModel(models) {
  // Prefer best available, fallback to any working
  const preferred = [
    'llama-3.3-70b-versatile',
    'llama-3.1-70b-versatile',
    'llama-3.1-8b-instant',
    'mixtral-8x7b-32768',
    'llama2-70b-4096',
    'gemma-7b-it',
  ];
  for (const m of preferred) if (models.includes(m)) return m;
  return models[0] || GROQ_MODEL;
}

async function ensureSupportedModel(preferred) {
  const now = Date.now();
  if (_cachedModel && now - _cachedModelTs < MODEL_TTL_MS) return _cachedModel;
  try {
    const models = await fetchGroqModels();
    const model = preferred && models.includes(preferred)
      ? preferred
      : pickPreferredModel(models);
    _cachedModel = model;
    _cachedModelTs = now;
    return model;
  } catch (e) {
    // fallback to env or default
    return GROQ_MODEL;
  }
}
// Groq chat API (uses global fetch available in Node 18+/Next.js)

// ==== Build enhanced system prompt with venue context ====
function buildSystemPrompt(city, neighborhood, category, venues) {
  let prompt = "You are Marco, a helpful travel assistant. ";

  if (city) prompt += `You're helping with travel in ${city}. `;
  if (neighborhood) prompt += `Focus on the ${neighborhood} neighborhood. `;
  if (category) prompt += `The user is interested in ${category}. `;

  // STRICT VENUE USAGE - forces the AI to reference specific venues
  if (venues?.length > 0) {
    const venueList = venues.slice(0, 6).map((v, i) =>
      `${i + 1}. ${v.name || v.title} - ${v.description || v.address || 'Great spot'}`
    ).join('\n');

    prompt += `
CRITICAL: You MUST reference these specific venues in your response:
${venueList}

When answering questions about ${category || 'places'} in ${neighborhood ? neighborhood + ', ' : ''}${city},
always suggest from this list first. Be specific about names, details, and why they're good choices.`;
  }

  prompt += "\nProvide helpful, accurate travel advice. If you don't know something, admit it.";
  return prompt;
}

// ==== Helper: simple heuristic routing ====
function route(messages, overrides = {}) {
  // overrides can force a specific model (e.g. via UI button)
  if (overrides.forceModel) {
    return overrides.forceModel; // 'groq', 'llama3-70b-8192', 'mixtral-8x7b-32768', etc.
  }

  // Look at the *last* user message for clues
  const last = messages[messages.length - 1];
  const txt = (last?.content ?? '').toLowerCase();

  // Travel-specific: always use the fast model unless asked otherwise
  if (txt.includes('history') || txt.includes('culture') || txt.includes('who is')) return 'llama3-70b-8192';
  if (txt.includes('price') || txt.includes('budget') || txt.includes('cheapest')) return 'mixtral-8x7b-32768';
  // default: best-quality travel model
  return 'llama3-70b-8192';
}

// ==== LLM callers ====
async function callGroq(messages, model) {
  const useModel = await ensureSupportedModel(model || GROQ_MODEL);
  const resp = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${GROQ_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: useModel,
      messages: messages.map(m => ({
        role: m.role === 'assistant' ? 'assistant' : 'user',
        content: m.content,
      })),
      temperature: 0.7,
      max_tokens: 1024,
    }),
  });

  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`Groq API error ${resp.status}: ${txt}`);
  }

  const data = await resp.json();
  return data.choices?.[0]?.message?.content ?? 'No Groq response';
}

// ==== Main handler ====
export default async function handler(req, res) {
  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  // Handle preflight
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method Not Allowed' });
  }

  try {
    const {
      messages,
      city,
      neighborhood,
      category,
      venues,
      session_id,
      forceModel,
    } = req.body;

    // Validate input
    if (!messages || !Array.isArray(messages)) {
      return res.status(400).json({ error: 'Messages array is required' });
    }

    // Generate or use existing session_id
    const currentSessionId = session_id || `sess_${Date.now()}`;
    
    // Check request limit per session
    const requestCount = sessionRequestCounts.get(currentSessionId) || 0;
    if (requestCount >= MAX_REQUESTS_PER_SESSION) {
      return res.status(429).json({ 
        error: 'Request limit reached',
        message: 'You have reached the limit of 1 AI request per session. Please start a new session to continue.',
        session_id: currentSessionId,
        limitReached: true
      });
    }

    // Build the system prompt with travel context
    const systemPrompt = buildSystemPrompt(city, neighborhood, category, venues);

    // Prepare messages for Groq (add system message)
    const groqMessages = [
      { role: 'system', content: systemPrompt },
      ...messages.map(msg => ({
        role: msg.role,
        content: msg.text || msg.content
      }))
    ];


    // Choose model using routing
    const model = route(messages, { forceModel });

    // Call Groq API (with evergreen model selection)
    let answer = null, usedModel = null, usage = null;
    try {
      const useModel = await ensureSupportedModel(model);
      const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${GROQ_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: useModel,
          messages: groqMessages,
          temperature: 0.7,
          max_tokens: 1024,
          stream: false,
        }),
      });
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Groq API error:', response.status, errorText);
        return res.status(502).json({
          error: `Groq API error: ${response.status}`,
          details: errorText.slice(0, 200)
        });
      }
      const data = await response.json();
      answer = data.choices[0].message.content;
      usedModel = useModel;
      usage = data.usage;
      
      // Increment request count for this session after successful API call
      sessionRequestCounts.set(currentSessionId, requestCount + 1);
    } catch (err) {
      console.error('Groq evergreen model error:', err);
      return res.status(502).json({ error: 'Groq evergreen model error', details: err.message });
    }

    // Return success response
    return res.status(200).json({
      answer,
      session_id: currentSessionId,
      model: usedModel,
      usage,
      requestsRemaining: MAX_REQUESTS_PER_SESSION - (requestCount + 1)
    });

  } catch (error) {
    console.error('Chat API error:', error);
    return res.status(500).json({
      error: 'Internal server error',
      details: error.message
    });
  }
}
