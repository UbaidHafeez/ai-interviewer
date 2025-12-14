from flask import Flask, request, jsonify
import json
import os
import sqlite3
from datetime import datetime
from flask_cors import CORS
from pyngrok import ngrok
import google.generativeai as genai
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv('.env.local')

# Initialize Flask App
app = Flask(__name__)
CORS(app)

# Initialize Gemini Client (Native Google SDK)
api_key = os.getenv('GEMINI_API_KEY')
if api_key:
    genai.configure(api_key=api_key)
    # Use the available model alias
    model = genai.GenerativeModel('gemini-flash-latest')
    print("[OK] Gemini Client initialized (Native SDK)")
else:
    print("[WARNING] GEMINI_API_KEY not found. AI features will fail.")
    model = None

# ---------------- DATABASE SETUP ---------------- #

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webhook_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_json TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_name TEXT,
            topic TEXT,
            start_time TEXT,
            end_time TEXT,
            score INTEGER,
            report_json TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            sender TEXT,
            text TEXT,
            analysis_json TEXT,
            timestamp TEXT,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ---------------- HELPER FUNCTIONS ---------------- #

def generate_ai_response(system_prompt, user_prompt, json_mode=True):
    """Generate response using Native Gemini SDK"""
    if not model:
        print("[ERROR] Gemini model not initialized", file=sys.stderr)
        return None
    try:
        print(f"[AI] Calling Gemini API...", file=sys.stderr)
        
        full_prompt = f"{system_prompt}\n\nUser Input: {user_prompt}\n\nIMPORTANT: Respond ONLY with valid JSON."
        
        response = model.generate_content(
            full_prompt,
            generation_config={"response_mime_type": "application/json"} if json_mode else {}
        )
        
        print(f"[OK] Gemini Response Received", file=sys.stderr)
        content = response.text.strip()
        
        # Clean up markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        return json.loads(content) if json_mode else content
    except Exception as e:
        print(f"[ERROR] AI Error: {e}", file=sys.stderr)
        return None

# ---------------- API ENDPOINTS ---------------- #

@app.route('/api/start', methods=['GET', 'POST'])
@app.route('/start_interview', methods=['GET', 'POST'])
def start_interview():
    print("[START] /api/start called!", file=sys.stderr)
    
    if request.method == 'POST':
        data = request.json or {}
    else:
        data = request.args.to_dict()
    
    candidate_name = data.get('name', 'Candidate')
    topic = data.get('topic', 'General Interview')
    language_code = data.get('language_code', 'en-US')
    resume_text = data.get('resume_text', '')

    # Create Session
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (candidate_name, topic, start_time) VALUES (?, ?, ?)",
        (candidate_name, topic, datetime.now().isoformat())
    )
    session_id = cursor.lastrowid
    
    # Persist Resume/Context as the first 'hidden' message so it's available in history
    context_message = f"Context: Role: {topic}. Target Language: {language_code}. Resume/CV: {resume_text}"
    cursor.execute(
        "INSERT INTO messages (session_id, sender, text, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, 'system', context_message, datetime.now().isoformat())
    )
    
    conn.commit()
    conn.close()

    # Generate Initial Questions with Language Output
    system_prompt = f"""You are a professional, humanoid interview agent. 
    Your tone: Polite, professional, yet warm and encouraging.
    Context: The user has applied for the role of '{topic}'.
    Task: 
    1. Welcome the candidate in their preferred language ({language_code}).
    2. Acknowledge their resume (if provided).
    3. Ask the FIRST relevant interview question based on the resume/role.
    
    Output: JSON with 'intro_message' (your spoken greeting + first question), 'language_code' ({language_code}).
    """
    
    user_prompt = f"Candidate: {candidate_name}, Role: {topic}, Language: {language_code}. Resume: {resume_text}. Start the interview."
    
    try:
        ai_data = generate_ai_response(system_prompt, user_prompt)
    except Exception:
        ai_data = None

    if not ai_data:
        # Fallback if AI fails
        lang_greetings = {
            'es-ES': "Hola", 'fr-FR': "Bonjour", 'de-DE': "Hallo", 'hi-IN': "Namaste", 'zh-CN': "Ni Hao", 'ja-JP': "Konnichiwa"
        }
        greeting = lang_greetings.get(language_code, "Hello")
        
        fallback_msg = f"{greeting} {candidate_name}. I have reviewed your application for the {topic} role. Let's begin. Tell me about your experience."
        
        ai_data = {
            "intro_message": fallback_msg,
            "questions": [{"id": 1, "text": "Tell me about your experience."}],
            "language_code": language_code
        }

    # Extract first question text safely
    question_text = ai_data.get('intro_message', "Ready.")
    # If there is a specific question list, maybe use that?
    # Actually, let's just use the intro_message as the spoken text.
    if ai_data.get('questions') and isinstance(ai_data['questions'], list) and len(ai_data['questions']) > 0:
        # We might want the first question to simply be the language check.
        # Let's trust the AI's intro_message which usually includes the question.
        pass

    return jsonify({
        "session_id": session_id,
        "intro_message": ai_data.get('intro_message'),
        "message": ai_data.get('intro_message'),
        "question": ai_data.get('intro_message'), # Use intro as the first spoken text
        "questions": ai_data.get('questions'),
        "language_code": ai_data.get('language_code', 'en-US'),
        "duration": 15,
        "timeline_minutes": []
    })

@app.route('/api/analyze', methods=['GET', 'POST'])
@app.route('/analyze_answer', methods=['GET', 'POST'])
@app.route('/next', methods=['GET', 'POST']) # Match frontend
def analyze_answer():
    data = request.json
    session_id = data.get('session_id', 1) # Default to 1 if missing
    answer_text = data.get('answer_text') or data.get('answer') # Match frontend 'answer'
    
    # Save User Answer
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (session_id, sender, text, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, 'user', answer_text, datetime.now().isoformat())
    )
    conn.commit()

    # Fetch Conversation History for Context
    cursor.execute("SELECT sender, text FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    history_rows = cursor.fetchall()
    
    # Format history for the AI
    history_text = ""
    for row in history_rows:
        if row['sender'] == 'system':
            history_text += f"[System Context]: {row['text']}\n"
        else:
            role = "Candidate" if row['sender'] == 'user' else "Interviewer"
            history_text += f"{role}: {row['text']}\n"

    # Analyze Answer with Context
    system_prompt = """You are a professional, humanoid interview agent.
    Role: You are interviewing a candidate.
    
    Capabilities:
    1. Multi-language: ADAPT to the language found in the conversation history. If the context says 'Target Language: es-ES', speak Spanish.
    2. Context: Use the conversation history (including Resume context) to ask relevant, probing questions.
    
    Rules:
    - Acknowledge the answer deeply.
    - Ask ONE follow-up or new question.
    - Keep responses concise (spoken style).
    
    Output: JSON with:
    - 'analysis' (score=null, feedback=null)
    - 'next_question' (The text you will speak/show)
    - 'language_code' (The IETF code for the language you are speaking).
    """
    
    user_prompt = f"""
    History:
    {history_text}
    
    Current Answer: {answer_text}
    
    Task: Respond naturally, switching language if requested, and ask the next question or give the first interview question.
    """
    
    try:
        ai_data = generate_ai_response(system_prompt, user_prompt)
    except Exception:
        ai_data = None

    if not ai_data:
        ai_data = {
            "analysis": {"score": None, "feedback": None, "suggestions": []},
            "next_question": "Could you elaborate on that?",
            "language_code": "en-US"
        }

    # Save Analysis
    cursor.execute(
        "UPDATE messages SET analysis_json = ? WHERE session_id = ? AND text = ?",
        (json.dumps(ai_data.get('analysis')), session_id, answer_text)
    )
    
    # Save AI Response to History (So we have it for next time context)
    ai_reply_text = ai_data.get('next_question')
    if ai_reply_text:
        cursor.execute(
            "INSERT INTO messages (session_id, sender, text, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, 'ai', ai_reply_text, datetime.now().isoformat())
        )

    conn.commit()
    conn.close()

    # Add 'reply' field for frontend
    ai_data['reply'] = ai_data.get('next_question')

    return jsonify(ai_data)

@app.route('/api/end', methods=['GET', 'POST'])
@app.route('/end_interview', methods=['GET', 'POST'])
def end_interview():
    print("[END] /end_interview called", file=sys.stderr)
    data = request.json or {}
    session_id = data.get('session_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE session_id = ?", (session_id,))
    messages = [dict(row) for row in cursor.fetchall()]
    
    transcript = [m['text'] for m in messages]
    
    system_prompt = """You are an interview agent.
    Job: Generate a final report based on the transcript.
    Output: JSON with 'overall_score' (0-10), 'summary', 'strengths', 'weaknesses', 'action_plan'.
    """
    
    user_prompt = f"Transcript: {json.dumps(transcript)}. Generate final report."
    
    try:
        report_data = generate_ai_response(system_prompt, user_prompt)
    except Exception:
        report_data = None

    if not report_data:
        report_data = {"overall_score": 0, "summary": "Could not generate report."}

    cursor.execute(
        "UPDATE sessions SET end_time = ?, score = ?, report_json = ? WHERE id = ?",
        (datetime.now().isoformat(), report_data.get('overall_score', 0), json.dumps(report_data), session_id)
    )
    conn.commit()
    conn.close()
    
    return jsonify(report_data)

@app.route('/api/history', methods=['GET'])
def get_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY start_time DESC")
    sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(sessions)

if __name__ == '__main__':
    print("[SERVER] Flask Server Starting...")
    # Ngrok disabled
    # try:
    #     public_url = ngrok.connect(8000).public_url
    #     print(f"[INFO] Public URL: {public_url}")
    # except Exception as e:
    #     print(f"[WARNING] Ngrok Error: {e}")
    app.run(port=8000, debug=True)
