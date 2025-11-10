"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

# FocusAI Schemas

class User(BaseModel):
    name: Optional[str] = Field(None, description="Full name")
    email: Optional[str] = Field(None, description="Email address")
    device_id: str = Field(..., description="Client-generated device identifier")
    voice: Optional[str] = Field("Cluely", description="Selected assistant voice/persona")

class Session(BaseModel):
    user_id: str = Field(..., description="User identifier (device-scoped for prototype)")
    goal: str = Field(..., description="User's task goal prompt")
    duration_minutes: int = Field(..., ge=1, le=480, description="Planned session length in minutes")
    categories: List[str] = Field(default_factory=list, description="Distraction categories to block")
    voice: Optional[str] = Field("Cluely", description="Assistant voice/persona")
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_focus_seconds: int = 0
    total_idle_seconds: int = 0
    distractions_blocked: int = 0
    status: Literal["active", "ended"] = "active"

class ActivityEvent(BaseModel):
    session_id: str = Field(..., description="Related session id")
    user_id: str = Field(...)
    timestamp: datetime = Field(...)
    device: Optional[str] = Field("web", description="Device label")
    app: Optional[str] = Field(None, description="App name if available")
    url: Optional[str] = Field(None, description="Active URL if in browser")
    title: Optional[str] = Field(None, description="Window/tab title")
    idle: bool = Field(False, description="Whether this represents inactivity")
    decision: Optional[Literal["relevant", "irrelevant"]] = None
    reason: Optional[str] = None

# Example schemas kept for reference
class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
