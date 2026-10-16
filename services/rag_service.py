import os
from google import genai
from services.embedding_service import embed_question, get_collection
from flask import current_app

def classify_intent(question, api_key, model_name):
    prompt = f"""Classify the user's question into exactly one of these categories:
GENERAL_LEGAL
DOCUMENT_SPECIFIC
GENERAL_KNOWLEDGE
PERSONAL_DOCUMENT_QUERY

Question: "{question}"

Rules:
- If asking about a general legal concept (e.g. "What is an NDA?"), return GENERAL_LEGAL.
- If asking about their uploaded document or resume (e.g. "What does my contract say?", "Summarize my resume"), return DOCUMENT_SPECIFIC.
- Only output the category name, nothing else.
"""
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        cat = response.text.strip().upper()
        if "DOCUMENT" in cat:
            return "DOCUMENT_SPECIFIC"
        return "GENERAL_LEGAL"
    except Exception:
        return "GENERAL_LEGAL"

def answer_question(user_id, question, document_id=None):
    try:
        api_key = current_app.config.get('GEMINI_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured. Check your .env file.")

        model_name = current_app.config.get('AI_MODEL', 'gemini-3.6-flash')
        print("LexAI model:", model_name)
        client = genai.Client(api_key=api_key)

        question_embedding = embed_question(question)
        collection = get_collection()
        
        context_blocks = []
        sources = []
        
        raw_results = []

        if document_id:
            # Specific Document Chat: Retrieve only user's private document chunks
            where_filter = {
                "$and": [
                    {"user_id": {"$eq": int(user_id)}},
                    {"document_id": {"$eq": str(document_id)}}
                ]
            }
            results = collection.query(
                query_embeddings=[question_embedding],
                n_results=8,
                where=where_filter
            )
            raw_results.append((results, "document"))
        else:
            # General Chat Mode
            intent = "GENERAL_LEGAL"
            
            if intent == 'DOCUMENT_SPECIFIC':
                # Query user's private documents
                user_filter = {"user_id": {"$eq": int(user_id)}}
                results = collection.query(
                    query_embeddings=[question_embedding],
                    n_results=8,
                    where=user_filter
                )
                raw_results.append((results, "document"))
            else:
                # Query Knowledge Base
                kb_filter = {"source_type": {"$eq": "knowledge_base"}}
                results = collection.query(
                    query_embeddings=[question_embedding],
                    n_results=8,
                    where=kb_filter
                )
                raw_results.append((results, "knowledge_base"))

        seen_chunks = set()
        combined_docs = []
        for res, default_type in raw_results:
            docs = res.get('documents', [[]])[0]
            metas = res.get('metadatas', [[]])[0]
            dists = res.get('distances', [[]])[0] if 'distances' in res and res['distances'] else [0]*len(docs)
            
            for d, m, dist in zip(docs, metas, dists):
                if dist > 2.2:  
                    continue
                if d in seen_chunks:
                    continue
                seen_chunks.add(d)
                combined_docs.append({"doc": d, "meta": m, "dist": dist, "default_type": default_type})
                
        combined_docs.sort(key=lambda x: x["dist"])
        
        source_idx = 1
        for item in combined_docs:
            d = item["doc"]
            meta = item["meta"]
            
            if meta.get("source_type") == "knowledge_base" or item["default_type"] == "knowledge_base":
                title = meta.get('title', 'Legal KB')
                context_blocks.append(f"Source {source_idx}: {title} — Knowledge Base\n{d}")
                sources.append({
                    "knowledge_base_id": meta.get('knowledge_base_id'),
                    "filename": title,
                    "chunk_id": meta.get('chunk_index'),
                    "category": meta.get('category'),
                    "source": meta.get('source'),
                    "type": "knowledge_base",
                    "title": title
                })
            else:
                filename = meta.get('filename', 'Unknown')
                context_blocks.append(f"Source {source_idx}: {filename} — Document\n{d}")
                sources.append({
                    "document_id": meta.get('document_id'),
                    "filename": filename,
                    "chunk_id": meta.get('chunk_index'),
                    "type": "document",
                    "title": filename
                })
            source_idx += 1
            
        
        if not context_blocks:
            # Keep document questions grounded in the uploaded document
            if document_id or intent == "DOCUMENT_SPECIFIC":
                return {
                    "answer": "I couldn't find enough relevant information in the selected document or available sources to answer reliably.",
                    "sources": []
                }

            # Answer general legal questions even when the Knowledge Base has no matching article
            general_prompt = f"""You are LexAI, an AI legal information assistant.

Answer the user's general legal question in simple, clear language.
Provide a useful definition, explanation, and example where appropriate.
Assume the user is asking about Indian law unless they specify another jurisdiction.
Do not invent legal sections, cases, penalties, or procedures.
If a legal detail is uncertain, say so clearly.
This is general legal information, not personalized legal advice.

User question: {question}

End with this disclaimer:
This information is AI-generated for educational and informational purposes only and does not constitute professional legal advice. Laws vary by jurisdiction and circumstances. Consult a qualified legal professional for advice about your specific situation.
"""
            response = client.models.generate_content(
                model=model_name,
                contents=general_prompt
            )

            return {
                "answer": response.text,
                "sources": []
            }

            
        context_text = "\n\n".join(context_blocks)
        
        prompt = f"""You are LexAI, an AI legal information assistant.

Your purpose is to explain legal concepts accurately, clearly, and comprehensively using the available trusted sources.
Answer the user's actual question directly.
For complex questions, provide a structured and detailed explanation.
Do not artificially shorten an answer when the available source material supports a more complete explanation.

Do not invent laws, sections, cases, penalties, procedures, deadlines, legal rights, or obligations.
Every factual legal claim should be supported by retrieved sources whenever the system is operating in grounded/RAG mode.
If the available sources are insufficient, explicitly say that the available sources do not contain enough information.
Do not pretend that unsupported information came from a source.

Distinguish between:
1. Knowledge Base information
2. User's uploaded document information
3. General explanatory information

Never cite a source that was not actually retrieved.
Never use an unrelated user document as a source for a general legal question.
Do not provide personalized legal advice.
Do not claim to be a lawyer.
Where jurisdiction matters, clearly mention it.
Where the source specifies a jurisdiction, preserve that jurisdiction.
Explain difficult legal terminology in simple language.
Use examples when they improve understanding.
Provide balanced explanations and mention important limitations.

When appropriate, structure answers like:
# Direct Answer
# What Does It Mean?
# Detailed Explanation
# Key Elements
# Types
# Example
# Rights and Obligations
# Legal Consequences
# Remedies / Legal Options
# Exceptions / Limitations
# Practical Considerations
# Related Concepts
# Sources
# Disclaimer

DO NOT force irrelevant sections into every answer. Do not repeat information just to increase length.
Do not impose a fixed word count. Use dynamic depth based on the question (200-1500+ words depending on complexity).
Every legal answer MUST end with this exact disclaimer: "This information is AI-generated for educational and informational purposes only and does not constitute professional legal advice. Laws vary by jurisdiction and circumstances. Consult a qualified legal professional for advice about your specific situation."

RETRIEVED CONTEXT:
{context_text}
 
USER QUESTION:
{question}
"""
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        
        return {
            "answer": response.text,
            "sources": sources
        }
        
    except Exception as e:
        import logging
        import traceback
        error_msg = f"RAG Error: {e}\n{traceback.format_exc()}"
        logging.error(error_msg)
        # Check for quota issues specifically
        if "429" in str(e) or "quota" in str(e).lower() or "503" in str(e):
            fallback_res = construct_fallback_response(context_blocks, sources, question)
            if fallback_res:
                return fallback_res
                
            if not context_blocks:
                return {
                    "answer": "I couldn't find enough relevant information in the LexAI Knowledge Base to answer this reliably, and the AI service is currently unavailable.",
                    "sources": []
                }
                
            raise RuntimeError("The AI service is currently busy or out of quota. Please try again later.")
            
        raise RuntimeError(f"An error occurred while processing your request: {str(e)}")

def construct_fallback_response(context_blocks, sources, question=""):
    import re
    
    source_titles = set()
    is_kb = False
    
    # Categories to extract
    direct_answers = []
    key_points = []
    remedies = []
    
    question_lower = question.lower()
    
    for block in context_blocks:
        lines = block.split('\n')
        if not lines: continue
        
        first_line = lines[0]
        title = "LexAI Source"
        if "Knowledge Base" in first_line:
            is_kb = True
            parts = first_line.split(":")
            if len(parts) > 1:
                raw = parts[1]
                if "—" in raw: title = raw.split("—")[0].strip()
                elif "-" in raw: title = raw.split("-")[0].strip()
                else: title = raw.replace("Knowledge Base", "").strip()
        elif "Document" in first_line:
            # We don't use document chat for fallback here
            pass
            
        if "Knowledge Base" in first_line:
            source_titles.add(title)
            content = "\n".join(lines[1:]).strip()
            
            # Extract sections separated by --- # Heading or just # Heading
            sections = re.split(r'\n-+\s*#+\s*|\n#+\s*', '\n' + content)
            
            for sec in sections:
                sec = sec.strip()
                if not sec: continue
                
                sec_lines = sec.split('\n')
                heading = sec_lines[0].lower().strip()
                body = "\n".join(sec_lines[1:]).strip()
                
                if not body:
                    body = heading
                    heading = "general"
                
                # Clean up body: remove stray ---
                body = re.sub(r'^-{3,}\s*$', '', body, flags=re.MULTILINE).strip()
                
                if "explanation" in heading or "definition" in heading:
                    direct_answers.append(body)
                elif "remed" in heading or "consequence" in heading:
                    remedies.append(body)
                else:
                    if heading != 'general':
                        key_points.append(f"**{heading.title()}**\n{body}")
                    else:
                        key_points.append(body)

    if not is_kb:
        return None

    # Filter based on question relevance if applicable
    if "remed" in question_lower or "consequence" in question_lower:
        # Prioritize remedies
        if remedies:
            direct_answers = remedies
            remedies = []
    elif "element" in question_lower or "type" in question_lower or "categor" in question_lower:
        # Let key points take priority
        pass

    fallback = "*(The AI service is currently unavailable. The following information is retrieved directly from the LexAI Knowledge Base.)*\n\n"
    
    # Cap limits
    def truncate_text(text, max_words=200):
        words = text.split()
        if len(words) > max_words:
            return " ".join(words[:max_words]) + "..."
        return text

    content_added = False
    
    if direct_answers:
        fallback += "### Direct Answer\n" + truncate_text("\n\n".join(direct_answers), 250) + "\n\n"
        content_added = True
    
    if key_points:
        fallback += "### Key Information\n" + truncate_text("\n\n".join(key_points), 250) + "\n\n"
        content_added = True
        
    if remedies:
        fallback += "### Remedies / Consequences\n" + truncate_text("\n\n".join(remedies), 150) + "\n\n"
        content_added = True
        
    if not content_added:
        fallback += "\n\n".join(context_blocks).replace("--- #", "###") + "\n\n"
        
    fallback += "### Source\nLexAI Knowledge Base\n"
    if source_titles:
        fallback += "Article(s): " + ", ".join(source_titles) + "\n\n"
        
    fallback += "*Note: This is general legal information retrieved deterministically, not professional legal advice.*"
    
    return {
    "answer": fallback,
    "sources": sources
}
