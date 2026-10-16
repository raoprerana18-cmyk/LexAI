import os
import json
from flask import current_app
from google import genai
from google.genai import types

def prepare_text_for_analysis(text):
    if not text:
        return ""
    # Very basic cleanup and truncation. 
    # Gemini 2.5 Flash has a ~1 million token limit, but let's truncate to 500,000 characters just to be extremely safe for Phase 3.
    # We could do better chunking, but for a simple MCA project, a hard truncation is fine.
    text = text.strip()
    max_chars = 500000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[TEXT TRUNCATED DUE TO LENGTH LIMITS]"
    return text

def analyze_legal_document(text):
    api_key = current_app.config.get('GEMINI_API_KEY')
    model_name = current_app.config.get('AI_MODEL', 'gemini-2.5-flash')
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")
        
    cleaned_text = prepare_text_for_analysis(text)
    if not cleaned_text:
        raise ValueError("No text provided for analysis.")

    prompt = """
    You are an AI Legal Assistant. Your task is to analyze the following legal document and extract key information into a structured JSON format.
    
    CRITICAL INSTRUCTIONS:
    - Analyze ONLY the supplied document text.
    - Clearly distinguish facts from interpretation.
    - DO NOT invent clauses, dates, parties, or information. If information is missing, use empty arrays [] or empty strings "".
    - You are NOT a lawyer. State that this is an AI analysis and not professional legal advice in the disclaimer.
    - You MUST output ONLY valid JSON.
    
    Expected JSON Structure:
    {
        "document_type": "string (e.g., Non-Disclosure Agreement, Employment Contract)",
        "summary": "string (executive summary)",
        "parties": ["string", "string"],
        "key_clauses": [
            {"title": "string", "explanation": "string"}
        ],
        "important_dates": [
            {"date": "string", "event": "string"}
        ],
        "obligations": [
            {"party": "string", "obligation": "string", "deadline": "string or null"}
        ],
        "risks": [
            {"description": "string", "severity": "LOW|MEDIUM|HIGH|CRITICAL"}
        ],
        "red_flags": [
            {"issue": "string", "explanation": "string"}
        ],
        "financial_terms": [
            {"amount": "string", "conditions": "string", "penalties": "string or null"}
        ],
        "termination_conditions": ["string", "string"],
        "rights": ["string", "string"],
        "recommendations": ["string", "string"],
        "confidence": "HIGH|MEDIUM|LOW",
        "disclaimer": "string"
    }
    
    Document Text:
    ---
    """ + cleaned_text

    import time
    
    try:
        client = genai.Client(api_key=api_key)
        
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Using structured output config to enforce JSON
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
                
                response_text = response.text
                if not response_text:
                    raise ValueError("Empty response from AI API.")
                    
                parsed_json = json.loads(response_text)
                return parsed_json
                
            except Exception as e:
                error_str = str(e)
                print("GEMINI ERROR:", repr(e))
                is_temporary = any(x in error_str.upper() for x in ["429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "TIMEOUT"])
                
                if is_temporary and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                
                if isinstance(e, json.JSONDecodeError):
                    raise ValueError(f"Failed to parse JSON from AI response: {str(e)}")
                    
                if is_temporary:
                    raise ValueError(f"AI analysis is temporarily unavailable because the AI service is currently busy. Please try again later.")
                
                raise ValueError(f"AI Analysis failed: {error_str}")

    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"AI Analysis failed: {str(e)}")
