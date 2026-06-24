"""
Business Schemas
Pydantic schemas for Business API operations.
"""
from typing import Literal
from uuid import UUID
from pydantic import Field


from app.schemas.common import BaseSchema, IDSchema, TimestampSchema


# ============================================================
# Supported Business Types
# ============================================================
BusinessType = Literal[
    "food_and_beverage",
    "saas",
    "retail",
    "b2b_services",
    "hospitality",
]


# ============================================================
# Base Business Schema
# ============================================================
class BusinessBase(BaseSchema):
    """Base business fields."""
    name: str = Field(..., min_length=2, max_length=255)
    business_type: BusinessType
    industry: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=255)
    country_code: str | None = Field(None, min_length=2, max_length=2)


# ============================================================
# Input: Create Business
# ============================================================
class BusinessCreate(BusinessBase):
    """
    Schema for creating a new business.
    Used in: POST /businesses
    """
    business_metadata: dict = Field(default_factory=dict)


# ============================================================
# Input: Update Business
# ============================================================
class BusinessUpdate(BaseSchema):
    """
    Schema for updating business details.
    All fields optional - partial update.
    """
    name: str | None = Field(None, min_length=2, max_length=255)
    business_type: BusinessType | None = None
    industry: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=255)
    country_code: str | None = Field(None, min_length=2, max_length=2)
    business_metadata: dict | None = None


# ============================================================
# Output: Business Response
# ============================================================
class BusinessResponse(BusinessBase, IDSchema, TimestampSchema):
    """
    Schema for returning business data.
    Used in: GET /businesses/{id}, POST /businesses response
    """
    owner_id: UUID  # UUID as string
    is_active: bool
    business_metadata: dict = Field(default_factory=dict)


# ============================================================
# Output: Business Summary (lightweight)
# ============================================================
class BusinessSummary(IDSchema):
    """
    Lightweight business representation for lists.
    Used when listing many businesses.
    """
    name: str
    business_type: BusinessType
    is_active: bool