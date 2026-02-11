# AKIM: Never display secrets. Only show masked values.
# Example masking: gsk_abc1****xyz9
# Use this for all troubleshooting, logs, and error output.

def mask_secret(value: str) -> str:
    if not value or len(value) < 12:
        return "****MASKED****"
    return f"{value[:6]}****{value[-4:]}"

# Usage example:
# print(f"GROQ_API_KEY: {mask_secret(os.getenv('GROQ_API_KEY'))}")
