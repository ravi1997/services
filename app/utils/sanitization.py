"""
Input sanitization and validation utilities.
"""
import bleach
import re
import logging

logger = logging.getLogger('app')

def sanitize_text(content):
    """
    Sanitize text content to remove all HTML tags and strictly clean it.
    Returns cleaned string.
    """
    if not isinstance(content, str):
        return str(content)
        
    # Strip all tags
    cleaned = bleach.clean(content, tags=[], strip=True)
    return cleaned

def validate_safe_input(content, context="unknown"):
    """
    Validates that input does not contain common attack vectors.
    Returns (is_safe: bool, reason: str).
    """
    if not isinstance(content, str):
        return True, None # Non-string input (like int) usually safe from XSS/SQLi in properly typed contexts
        
    # SQL Injection basic heuristic
    # (Note: App uses SQLAlchemy which protects against this, but good for defense in depth)
    sqli_patterns = [
        r"(?i)\b(union\s+select|select\s+.*\s+from|insert\s+into|delete\s+from|drop\s+table|update\s+.*set)\b",
        r"(?i)';\s*--", 
        r"(?i)'\s+or\s+1=1"
    ]
    for pattern in sqli_patterns:
        if re.search(pattern, content):
            logger.warning(f"Potential SQLi detected in {context}: {content[:50]}...")
            return False, "Potential security violation detected"
            
    # XSS / Script injection (heuristic for obvious attemps)
    xss_patterns = [
        r"(?i)<script.*?>",
        r"(?i)javascript:",
        r"(?i)onload=",
        r"(?i)onerror="
    ]
    for pattern in xss_patterns:
        if re.search(pattern, content):
            logger.warning(f"Potential XSS detected in {context}: {content[:50]}...")
            return False, "Potential security violation detected"

    return True, None
