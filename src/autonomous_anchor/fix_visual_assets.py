#!/usr/bin/env python3
"""Fix visual_assets.py to always generate placeholder images."""

import re

# Read the file
with open('src/autonomous_anchor/visual_assets.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the early return when verdicts is empty
old_code = '''    logger.info(f"[fetch_relevant_images] Starting with {len(verdicts)} verdicts, output_dir={output_dir}")
    
    if not verdicts:
        logger.warning("[fetch_relevant_images] No verdicts provided! Returning empty list")
        return []

    style_hints = ['''

new_code = '''    logger.info(f"[fetch_relevant_images] Starting with {len(verdicts or [])} verdicts, output_dir={output_dir}")

    style_hints = ['''

if old_code in content:
    content = content.replace(old_code, new_code)
    print("✓ Removed early return for empty verdicts")
else:
    print("✗ Could not find the early return pattern")

# Fix the terms extraction to handle empty verdicts  
old_terms = '''    try:
        terms = _extract_terms(verdicts)
    except Exception as e:
        logger.error(f"[fetch_relevant_images] CRITICAL: Failed to extract terms: {type(e).__name__}: {e}")
        terms = ["News Story"]  # Fallback default term
    
    logger.info(f"[fetch_relevant_images] Extracted {len(terms)} terms: {terms}")
    logger.info(f"[fetch_relevant_images] Attempting to fetch {max_images} images, will fallback to placeholders if needed")'''

new_terms = '''    # Extract terms from verdicts or use default fallback terms
    try:
        if verdicts:
            terms = _extract_terms(verdicts)
        else:
            logger.warning("[fetch_relevant_images] No verdicts provided, using default terms")
            terms = []
    except Exception as e:
        logger.error(f"[fetch_relevant_images] CRITICAL: Failed to extract terms: {type(e).__name__}: {e}")
        terms = []
    
    # Ensure we have at least some terms to work with
    if not terms:
        logger.warning("[fetch_relevant_images] No terms extracted, using default fallback terms")
        terms = ["News Story", "Breaking News", "Today's Story", "Latest Update"][:max_images]
    
    logger.info(f"[fetch_relevant_images] Using {len(terms)} terms: {terms}")
    logger.info(f"[fetch_relevant_images] Attempting to fetch {max_images} images, will fallback to placeholders if needed")'''

if old_terms in content:
    content = content.replace(old_terms, new_terms)
    print("✓ Fixed terms extraction for empty verdicts")
else:
    print("✗ Could not find terms extraction pattern")

# Write the file back
with open('src/autonomous_anchor/visual_assets.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ File updated successfully")
print("All verdicts, even empty ones, will now generate placeholder images")
