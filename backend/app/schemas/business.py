"""
Business Schemas
Pydantic schemas for Business API operations.
Updated: Flexible business types.
"""
from typing import Optional
from uuid import UUID
from pydantic import Field

from app.schemas.common import BaseSchema, IDSchema, TimestampSchema


# ============================================================
# Business Type (alias = str for flexibility)
# ============================================================
BusinessType = str


# ============================================================
# Base Business Schema
# ============================================================
class BusinessBase(BaseSchema):
    """Base business fields."""
    name: str = Field(..., min_length=2, max_length=255)
    business_type: str = Field(..., min_length=1, max_length=100)
    industry: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=255)
    country_code: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = Field(None, max_length=1000)


# ============================================================
# Input: Create Business
# ============================================================
class BusinessCreate(BusinessBase):
    """Schema for creating a new business."""
    business_metadata: Optional[dict] = Field(default_factory=dict)


# ============================================================
# Input: Update Business
# ============================================================
class BusinessUpdate(BaseSchema):
    """Schema for updating business details."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    business_type: Optional[str] = None
    industry: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=255)
    country_code: Optional[str] = Field(None, max_length=10)
    description: Optional[str] = None
    business_metadata: Optional[dict] = None


# ============================================================
# Output: Business Response
# ============================================================
class BusinessResponse(BusinessBase, IDSchema, TimestampSchema):
    """Schema for returning business data."""
    owner_id: UUID
    is_active: bool
    business_metadata: dict = Field(default_factory=dict)


# ============================================================
# Output: Business Summary
# ============================================================
class BusinessSummary(IDSchema):
    """Lightweight business representation for lists."""
    name: str
    business_type: str
    is_active: bool