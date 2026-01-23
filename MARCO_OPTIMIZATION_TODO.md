# Marco Optimization Plan - COMPLETED ✅

## Goal: Improve Marco's ability to hold real travel conversations

## Changes Implemented

### 1. Enhanced Conversation Memory ✅
Added `ConversationMemory` class in `semantic.py`:
- Tracks user interests across messages (coffee, food, bars, attractions, etc.)
- Stores topic transitions
- Builds context for coherent follow-up responses
- Detects when user is asking follow-up vs new topics

### 2. Improved Venue Context ✅
Enhanced `create_rich_venue_context()` function:
- Special handling for dark coffee queries
- Adds "why" context to recommendations
- Includes cuisine, features, address details
- Weather-aware suggestions

### 3. Natural Conversation Prompts ✅
Added `create_conversation_prompt()` function:
- System prompt establishes Marco's personality
- Explicit rules against generic responses
- Rules for multi-turn conversations
- Examples of GOOD vs BAD responses
- Follow-up question detection

### 4. Quick Venue Recommendations ✅
Added `create_venue_recommendation()` function:
- Concise venue listing for quick responses
- Includes name, cuisine, address
- Context-aware formatting

### 5. Test Endpoint ✅
Added `/marco-test` endpoint in `app.py`:
- Curl-friendly for testing
- Accepts q, city, venues, history, weather
- Returns conversation-style responses
- Debug info included

## Files Modified
- `/home/markm/TravelLand/city_guides/src/semantic.py` - Added ConversationMemory class and new functions
- `/home/markm/TravelLand/city_guides/src/app.py` - Added `/marco-test` endpoint

## Testing Commands

```bash
# Start the server
cd /home/markm/TravelLand/city_guides
python app.py

# Test 1: Basic query (without API key - fallback mode)
curl -X POST http://localhost:5010/marco-test \
  -H "Content-Type: application/json" \
  -d '{"q": "What are the best coffee shops?", "city": "London"}'

# Test 2: Dark coffee query with venues
curl -X POST http://localhost:5010/marco-test \
  -H "Content-Type: application/json" \
  -d '{
    "q": "Tell me about dark roast coffee",
    "city": "London",
    "venues": [
      {"name": "Blue Bottle Coffee", "type": "coffee", "cuisine": "specialty"},
      {"name": "Temple Coffee", "type": "cafe", "cuisine": "espresso"}
    ]
  }'

# Test 3: Multi-turn conversation simulation
curl -X POST http://localhost:5010/marco-test \
  -H "Content-Type: application/json" \
  -d '{
    "q": "What about dark roast?",
    "city": "London",
    "history": "User: What coffee shops?\nMarco: Try Blue Bottle\nUser: What about dark roast?"
  }'

# Test 4: Full conversation with venues and history
curl -X POST http://localhost:5010/marco-test \
  -H "Content-Type: application/json" \
  -d '{
    "q": "What should I try?",
    "city": "London",
    "venues": [
      {"name": "Blue Bottle", "type": "coffee", "cuisine": "specialty", "tags": {"cuisine": "specialty coffee", "outdoor_seating": "yes"}},
      {"name": "Temple Coffee", "type": "cafe", "cuisine": "espresso", "tags": {"cuisine": "single origin"}}
    ],
    "history": "User: Looking for coffee\nMarco: Blue Bottle is great"
  }'
```

## Expected Improvements

1. **No more generic responses** - Marco now references specific venues by name
2. **Follow-up awareness** - Marco remembers what user asked before
3. **Natural conversation** - Marco asks specific follow-up questions
4. **Interest tracking** - Marco learns user preferences (coffee, food, etc.)
5. **Context-aware** - Weather and venue data influence recommendations

## Debug Info

The `/marco-test` endpoint returns debug info:
- `mode`: "groq" or "no_api_key"
- `query`: Original user query
- `city`: City name
- `venues_count`: Number of venues provided
- `history_length`: Length of conversation history
- `is_followup`: Boolean indicating if this is a follow-up question

