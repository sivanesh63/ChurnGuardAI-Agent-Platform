import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)


def generate_call_script(customer_name: str = None, customer_data: dict = None, model=None) -> dict:
    """
    Generate a standard call script using LLM with greeting and feedback questions.
    Returns dict with 'greeting', 'feedback_question', and 'full_script'.
    Note: Greeting is standard/common for all users (no personalization).
    """
    if not model:
        logger.warning("No model provided for call script generation")
        return {
            "greeting": "Hello! This is a friendly call from our service team.",
            "feedback_question": "How would you rate your experience with our service on a scale of 1 to 5?",
            "full_script": "Hello! This is a friendly call from our service team. How would you rate your experience with our service on a scale of 1 to 5?"
        }
    
    prompt = """Generate a brief, friendly phone call script for customer service feedback collection.
Rules:
- Use a standard, generic greeting (do NOT use customer names, company names, or any personal details)
- Keep greeting under 15 seconds of speech
- Ask ONE clear feedback question about service quality
- Use natural, conversational tone
- Total script should be 30-45 seconds

Example format:
"Hello! This is a friendly call from our service team. We're reaching out to gather your valuable feedback."
Then ask: "How would you rate your recent experience with our service, and what can we improve?"

Return ONLY the script text, no explanations. Make it professional and generic for all customers."""
    
    try:
        response = model.generate_content(prompt)
        full_script = (response.text or "").strip()
        # Split into greeting and question if possible
        sentences = full_script.replace("?", ".").split(".")
        greeting = sentences[0].strip() if sentences else "Hello! This is a friendly call from ChurnGuard AI."
        feedback_question = sentences[1].strip() if len(sentences) > 1 else "How would you rate your experience with our service on a scale of 1 to 5?"
        
        return {
            "greeting": greeting,
            "feedback_question": feedback_question,
            "full_script": full_script
        }
    except Exception as e:
        logger.error(f"Error generating call script: {e}")
        return {
            "greeting": "Hello! This is a friendly call from ChurnGuard AI.",
            "feedback_question": "How would you rate your experience with our service on a scale of 1 to 5?",
            "full_script": "Hello! This is a friendly call from ChurnGuard AI. How would you rate your experience with our service on a scale of 1 to 5?"
        }

