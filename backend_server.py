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

# ---------------- NO DATABASE (STATELESS VERCEL VERSION) ---------------- #

@app.route('/', methods=['GET'])
def home():
    return "AI Interviewer Backend is Running on Vercel!"

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
            "language_code": language_code
        }

    return jsonify({
        "session_id": "vercel-stateless-session", 
        "intro_message": ai_data.get('intro_message'),
        "message": ai_data.get('intro_message'),
        "question": ai_data.get('intro_message'),
        "language_code": ai_data.get('language_code', 'en-US')
    })

@app.route('/api/analyze', methods=['GET', 'POST'])
@app.route('/analyze_answer', methods=['GET', 'POST'])
@app.route('/next', methods=['GET', 'POST']) 
def analyze_answer():
    data = request.json
    answer_text = data.get('answer_text') or data.get('answer')
    history = data.get('history', []) # Expect frontend to send history
    
    # Format history for the AI
    history_text = ""
    for msg in history:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        history_text += f"{role.upper()}: {content}\n"

    # Analyze Answer with Context
    system_prompt = """You are a professional, humanoid interview agent.
    Role: You are interviewing a candidate.
    
    Capabilities:
    1. Multi-language: ADAPT to the language found in the conversation history. If the context says 'Target Language: es-ES', speak Spanish.
    2. Context: Use the conversation history to ask relevant, probing questions.
    
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
    
    Task: Respond naturally, switching language if requested, and ask the next question.
    """
    
    try:
        ai_data = generate_ai_response(system_prompt, user_prompt)
    except Exception:
        ai_data = None

    if not ai_data:
        ai_data = {
            "analysis": {"score": None, "feedback": None},
            "next_question": "Could you elaborate on that?",
            "language_code": "en-US"
        }

    # Add 'reply' field for frontend
    ai_data['reply'] = ai_data.get('next_question')

    return jsonify(ai_data)

@app.route('/api/end', methods=['GET', 'POST'])
@app.route('/end_interview', methods=['GET', 'POST'])
def end_interview():
    print("[END] /end_interview called", file=sys.stderr)
    data = request.json or {}
    history = data.get('history', [])
    
    transcript = [msg.get('content') for msg in history]
    
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
    
    return jsonify(report_data)

@app.route('/api/history', methods=['GET'])
def get_history():
    # Vercel stateless version has no persistent history
    return jsonify([])

if __name__ == '__main__':
    print("[SERVER] Flask Server Starting Local...")
    app.run(port=8000, debug=True)
