"""
Normalize - Business Profile
============================
Normalize the target business profile from raw input.

Extracts:
- business_identity (name, type, etc.)
- contact_presence (phone, email, address)
- commercial (pricing, offerings)
- visual_identity
- brand_voice
- marketing_signals
"""
from app.preprocessing.normalize.helpers import safe_get


def normalize_business_profile(raw_data: dict, quality_report: dict) -> dict:
    """
    Extract and structure the business profile from raw input.
    
    Args:
        raw_data: Original raw input dict
        quality_report: Quality report to annotate
    
    Returns:
        Normalized business profile dict
    """
    # Extract sections (may use multiple possible key names)
    identity = safe_get(raw_data, ["business_identity", "identity", "profile"]) or {}
    contact = safe_get(raw_data, ["contact_presence", "contact"]) or {}
    commercial = safe_get(raw_data, ["commercial"]) or {}
    pricing = safe_get(commercial, ["pricing"]) or {}
    visual_identity = safe_get(raw_data, ["visual_identity"]) or {}
    brand_voice = safe_get(raw_data, ["brand_voice"]) or {}
    marketing_signals = safe_get(raw_data, ["marketing_signals"]) or {}
    offerings = safe_get(raw_data, ["offerings"]) or []
    
    # Extract business name
    business_name = (
        safe_get(identity, ["name", "business_name"])
        or safe_get(raw_data, ["business_name", "name"])
    )
    
    # Build unified business profile
    profile = {
        "business_identity": {
            "name": business_name,
            "type": safe_get(identity, ["type", "business_type", "category"]),
            "description": safe_get(identity, ["description", "about"]),
            "founded": safe_get(identity, ["founded", "founded_year", "established"]),
        },
        "contact_presence": {
            "phone": safe_get(contact, ["phone", "telephone", "mobile"]),
            "email": safe_get(contact, ["email"]),
            "address": safe_get(contact, ["address", "location"]),
            "city": safe_get(contact, ["city"]),
            "country": safe_get(contact, ["country"]),
            "website": safe_get(contact, ["website", "url"]),
            "social_media": safe_get(contact, ["social_media", "social"]) or {},
        },
        "commercial": {
            "pricing": {
                "tier": safe_get(pricing, ["tier", "price_tier", "price_level"]),
                "currency": safe_get(pricing, ["currency"]),
                "average_check": safe_get(pricing, ["average_check", "avg_price"]),
            },
            "offerings": offerings if isinstance(offerings, list) else [],
        },
        "visual_identity": {
            "logo_url": safe_get(visual_identity, ["logo_url", "logo"]),
            "primary_colors": safe_get(visual_identity, ["colors", "primary_colors"]) or [],
            "imagery_style": safe_get(visual_identity, ["imagery_style", "style"]),
        },
        "brand_voice": {
            "tone": safe_get(brand_voice, ["tone"]),
            "personality": safe_get(brand_voice, ["personality"]),
            "keywords": safe_get(brand_voice, ["keywords"]) or [],
        },
        "marketing_signals": {
            "campaigns": safe_get(marketing_signals, ["campaigns"]) or [],
            "promotions": safe_get(marketing_signals, ["promotions"]) or [],
            "channels": safe_get(marketing_signals, ["channels"]) or [],
        },
    }
    
    # Annotate quality issues
    if not business_name:
        quality_report["missing_fields"].append({
            "section": "business_identity",
            "field": "name",
            "issue": "Business name could not be extracted",
        })
    
    if not safe_get(contact, ["phone"]) and not safe_get(contact, ["email"]):
        quality_report["confidence_notes"].append({
            "level": "low",
            "issue": "no_contact_info",
            "message": "No phone or email found in business profile.",
        })
    
    return profile