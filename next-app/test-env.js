// Test environment variables
require('dotenv').config();

console.log('=== ENVIRONMENT TEST ===');
console.log('GROQ_API_KEY exists:', !!process.env.GROQ_API_KEY);
console.log('GROQ_API_KEY length:', process.env.GROQ_API_KEY?.length || 0);
console.log('GROQ_API_KEY starts with:', process.env.GROQ_API_KEY?.substring(0, 10) || 'undefined');

// Test Groq API call
async function testGroq() {
  try {
    const response = await fetch('https://api.groq.com/openai/v1/models', {
      headers: { Authorization: `Bearer ${process.env.GROQ_API_KEY}` },
    });
    
    console.log('Groq API status:', response.status);
    
    if (response.ok) {
      const data = await response.json();
      console.log('Groq models count:', data.data?.length || 0);
      console.log('First model:', data.data?.[0]?.id || 'none');
    } else {
      const errorText = await response.text();
      console.log('Groq API error:', errorText);
    }
  } catch (error) {
    console.error('Groq API test failed:', error);
  }
}

testGroq();
