import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)


def generate_call_script(customer_name: str = None, customer_data: dict = None, model=None) -> dict:
    """
    Generate a personalized call script using LLM with greeting and feedback questions.
    Returns dict with 'greeting', 'feedback_question', and 'full_script'.
    """
    if not model:
        logger.warning("No model provided for call script generation")
        return {
            "greeting": "Hello! This is a friendly call from ChurnGuard AI.",
            "feedback_question": "How would you rate your experience with our service on a scale of 1 to 5?",
            "full_script": "Hello! This is a friendly call from ChurnGuard AI. How would you rate your experience with our service on a scale of 1 to 5?"
        }
    
    customer_info = ""
    if customer_name:
        customer_info += f"Customer name: {customer_name}. "
    if customer_data:
        relevant_fields = ["SubscriptionType", "TenureMonths", "MonthlyCharges", "Location"]
        info_parts = [f"{k}: {customer_data.get(k, 'N/A')}" for k in relevant_fields if k in customer_data]
        if info_parts:
            customer_info += "Customer details: " + ", ".join(info_parts) + ". "
    
    prompt = f"""Generate a brief, friendly phone call script for customer service feedback collection.
Rules:
- Keep greeting under 15 seconds of speech
- Ask ONE clear feedback question about service quality
- Use natural, conversational tone
- Total script should be 30-45 seconds

{customer_info}
Create a warm greeting, then ask: "How would you rate your recent experience with our service, and what can we improve?"

Return ONLY the script text, no explanations."""
    
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

