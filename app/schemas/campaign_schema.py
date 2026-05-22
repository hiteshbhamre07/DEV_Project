from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


class CampaignBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = "draft"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    target_audience: Optional[str] = None
    budget: Optional[float] = None



class AssetCreate(BaseModel):
    name: str
    type: Optional[str] = None
    url: Optional[str] = None

class SegmentCreate(BaseModel):
    name: str
    job_titles: Optional[List[str]] = []
    industries: Optional[List[str]] = []
    geos: Optional[List[str]] = []
    suppression_lists: Optional[List[str]] = []
    target_company_lists: Optional[List[str]] = []
    lead_allocation: Optional[int] = None
    assets: Optional[List[AssetCreate]] = []

class CampaignCreate(CampaignBase):
    segments: Optional[List[SegmentCreate]] = []


class SegmentUpdate(BaseModel):
    id: Optional[int] = None
    name: str
    job_titles: Optional[List[str]] = []
    industries: Optional[List[str]] = []
    geos: Optional[List[str]] = []
    lead_allocation: Optional[int] = None
    assets: Optional[List[AssetCreate]] = []

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    target_audience: Optional[str] = None
    budget: Optional[float] = None
    segments: Optional[List[SegmentUpdate]] = None



class Asset(AssetCreate):
    id: int
    segment_id: int

    class Config:
        from_attributes = True

class Segment(SegmentCreate):
    id: int
    campaign_id: int
    assets: List[Asset] = []

    class Config:
        from_attributes = True

class Campaign(CampaignBase):
    id: int
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    is_active: bool = True
    segments: List[Segment] = []

    class Config:
        from_attributes = True
