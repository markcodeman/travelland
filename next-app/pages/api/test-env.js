export default async function handler(req, res) {
  console.log('=== ENV TEST ===');
  console.log('GROQ_API_KEY exists:', !!process.env.GROQ_API_KEY);
  console.log('GROQ_API_KEY length:', process.env.GROQ_API_KEY?.length || 0);
  console.log('GROQ_API_KEY starts with:', process.env.GROQ_API_KEY?.substring(0, 10) || 'undefined');
  console.log('GROQ_MODEL:', process.env.GROQ_MODEL);
  
  res.status(200).json({
    GROQ_API_KEY_exists: !!process.env.GROQ_API_KEY,
    GROQ_API_KEY_length: process.env.GROQ_API_KEY?.length || 0,
    GROQ_API_KEY_prefix: process.env.GROQ_API_KEY?.substring(0, 10) || 'undefined',
    GROQ_MODEL: process.env.GROQ_MODEL || 'undefined'
  });
}
