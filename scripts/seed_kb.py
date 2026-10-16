import os
import sys
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from app import create_app
from extensions import db
from models.database_models import KnowledgeBase, User
from services.embedding_service import index_kb_entry
from google import genai

TOPICS = [
    ("Contract basics", "Contract Law"),
    ("Essential elements of a contract", "Contract Law"),
    ("Offer and acceptance", "Contract Law"),
    ("Consideration", "Contract Law"),
    ("Capacity to contract", "Contract Law"),
    ("Free consent", "Contract Law"),
    ("Misrepresentation", "Contract Law"),
    ("Fraud", "Contract Law"),
    ("Coercion", "Contract Law"),
    ("Undue influence", "Contract Law"),
    ("Void agreements", "Contract Law"),
    ("Voidable contracts", "Contract Law"),
    ("Breach of contract", "Contract Law"),
    ("Remedies for breach", "Contract Law"),
    ("Indemnity", "Contract Law"),
    ("Guarantee", "Contract Law"),
    ("Bailment", "Contract Law"),
    ("Pledge", "Contract Law"),
    ("Agency", "Contract Law"),
    ("E-contracts", "Contract Law"),
    ("Non-Disclosure Agreements", "Contract Law"),
    ("Employment agreements", "Contract Law"),
    ("Civil disputes", "Civil Law"),
    ("Injunctions", "Civil Law"),
    ("Specific performance", "Civil Law"),
    ("Damages", "Civil Law"),
    ("Limitation concepts", "Civil Law"),
    ("Property disputes", "Civil Law"),
    ("Ownership", "Civil Law"),
    ("Possession", "Civil Law"),
    ("Transfer of property", "Civil Law"),
    ("Lease", "Civil Law"),
    ("Rent agreements", "Civil Law"),
    ("Power of attorney", "Civil Law"),
    ("Consumer rights", "Consumer Law"),
    ("Consumer definition", "Consumer Law"),
    ("Deficiency in service", "Consumer Law"),
    ("Defective goods", "Consumer Law"),
    ("Unfair trade practices", "Consumer Law"),
    ("Consumer complaints", "Consumer Law"),
    ("Consumer dispute resolution", "Consumer Law"),
    ("Product liability", "Consumer Law"),
    ("E-commerce consumer rights", "Consumer Law"),
    ("Company basics", "Corporate Law"),
    ("Private vs public company", "Corporate Law"),
    ("Directors", "Corporate Law"),
    ("Director duties", "Corporate Law"),
    ("Shareholders", "Corporate Law"),
    ("Corporate contracts", "Corporate Law"),
    ("Corporate compliance", "Corporate Law"),
    ("Insolvency basics", "Corporate Law"),
    ("Business disputes", "Corporate Law"),
    ("Copyright", "Intellectual Property"),
    ("Trademark", "Intellectual Property"),
    ("Patent", "Intellectual Property"),
    ("Trade secrets", "Intellectual Property"),
    ("Trademark infringement", "Intellectual Property"),
    ("Copyright infringement", "Intellectual Property"),
    ("Licensing", "Intellectual Property"),
    ("Intellectual property ownership", "Intellectual Property"),
    ("Cybercrime basics", "Cyber Law"),
    ("Data protection", "Cyber Law"),
    ("Privacy", "Cyber Law"),
    ("Electronic records", "Cyber Law"),
    ("Electronic signatures", "Cyber Law"),
    ("Online fraud", "Cyber Law"),
    ("Identity theft", "Cyber Law"),
    ("Unauthorized access", "Cyber Law"),
    ("Cybersecurity obligations", "Cyber Law"),
    ("Employment contracts", "Employment Law"),
    ("Salary disputes", "Employment Law"),
    ("Termination", "Employment Law"),
    ("Notice periods", "Employment Law"),
    ("Workplace harassment", "Employment Law"),
    ("Employee rights", "Employment Law"),
    ("Employer obligations", "Employment Law"),
    ("Leave and workplace policies", "Employment Law"),
    ("Criminal offence basics", "Criminal Law"),
    ("FIR", "Criminal Law"),
    ("Investigation", "Criminal Law"),
    ("Arrest", "Criminal Law"),
    ("Bail", "Criminal Law"),
    ("Anticipatory bail", "Criminal Law"),
    ("Criminal trial", "Criminal Law"),
    ("Evidence", "Criminal Law"),
    ("Criminal procedure", "Criminal Law"),
    ("Cyber offences", "Criminal Law"),
    ("Cheating", "Criminal Law"),
    ("Criminal breach of trust", "Criminal Law"),
    ("Defamation", "Criminal Law"),
    ("Theft", "Criminal Law"),
    ("Assault", "Criminal Law")
]

PROMPT_TEMPLATE = '''You are an expert Indian legal scholar. Your task is to write a highly detailed, accurate, and structured Knowledge Base article about '{title}' under the category '{category}'.

IMPORTANT RULES:
1. Prioritize current Indian law (e.g. BNS, BNSS, BSA instead of IPC/CrPC where applicable, Consumer Protection Act 2019, DPDP Act 2023, etc.).
2. Do NOT hallucinate section numbers or case names. If unsure, describe the general rule.
3. Keep the content comprehensive (500-1200 words) so it can be effectively retrieved via RAG.
4. Use standard Markdown formatting.

Structure the article using these headings (skip any that do not strictly apply):
# Definition
# Explanation
# Key Elements
# Types/Categories
# Examples
# Rights & Obligations
# Remedies / Consequences
# Important Exceptions
# Practical Considerations
# Related Concepts
'''

def main():
    app = create_app()
    with app.app_context():
        api_key = app.config.get('GEMINI_API_KEY') or os.getenv('GEMINI_API_KEY')
        client = genai.Client(api_key=api_key)
        admin = User.query.filter_by(role='admin').first()
        admin_id = admin.id if admin else None

        existing_titles = {kb.title for kb in KnowledgeBase.query.all()}
        
        print(f"Total topics to process: {len(TOPICS)}")
        success_count = 0

        for title, category in TOPICS:
            if title in existing_titles:
                print(f"Skipping '{{title}}', already exists.")
                continue
                
            print(f"Generating content for: {{title}} ({{category}})")
            prompt = PROMPT_TEMPLATE.format(title=title, category=category)
            
            try:
                response = client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=prompt
                )
                content = response.text
                
                source = "India Code / Official Acts"
                if category == "Criminal Law":
                    source = "BNS / BNSS / BSA (India)"
                elif category == "Contract Law":
                    source = "Indian Contract Act, 1872"
                elif category == "Consumer Law":
                    source = "Consumer Protection Act, 2019"
                elif category == "Corporate Law":
                    source = "Companies Act, 2013 / IBC"
                
                kb_entry = KnowledgeBase(
                    title=title,
                    category=category,
                    content=content,
                    source=source,
                    created_by=admin_id
                )
                db.session.add(kb_entry)
                db.session.commit()
                
                index_kb_entry(str(kb_entry.id), title, category, content, source)
                print(f"Successfully added & indexed: {{title}}")
                success_count += 1
                
            except Exception as e:
                print(f"Failed to process '{{title}}': {{str(e)}}")
                db.session.rollback()
            
            time.sleep(2)

        print(f"Finished. Successfully seeded {{success_count}} articles.")

if __name__ == '__main__':
    main()
