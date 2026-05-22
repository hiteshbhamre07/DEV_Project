from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, UniqueConstraint, Boolean, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    name = Column(String, nullable=False)  # Unified name field
    email = Column(String, nullable=False, index=True)
    domain = Column(String, nullable=True)
    primary_phone = Column(String, nullable=True)
    boardline_phone = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, processed, contacted, dead
    notes = Column(Text, nullable=True)
    
    # Raw data fields for 74-column CSV alignment
    campaign_name = Column(String, nullable=True)
    campaign_description = Column(Text, nullable=True)
    campaign_status = Column(String, nullable=True)
    
    company_name = Column(String, nullable=True)
    company_url = Column(String, nullable=True)
    company_location = Column(String, nullable=True)
    company_industry = Column(String, nullable=True)
    company_employee_size = Column(String, nullable=True)
    company_proof_links = Column(Text, nullable=True)
    
    campaign_order_id = Column(String, nullable=True)
    campaign_type = Column(String, nullable=True)
    campaign_segment = Column(String, nullable=True)
    campaign_asset_id = Column(String, nullable=True)
    
    job_level = Column(String, nullable=True)
    job_function = Column(String, nullable=True)
    job_department = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # FKs
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    job_profile_id = Column(Integer, ForeignKey("job_profiles.id"), nullable=True)
    scored_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    audit_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Intelligence
    cq1 = Column(Text, nullable=True)
    cq2 = Column(Text, nullable=True)
    cq3 = Column(Text, nullable=True)
    cq4 = Column(Text, nullable=True)
    cq5 = Column(Text, nullable=True)
    cq6 = Column(Text, nullable=True)
    cq7 = Column(Text, nullable=True)
    cq8 = Column(Text, nullable=True)
    cq9 = Column(Text, nullable=True)
    cq10 = Column(Text, nullable=True)
    call_recording = Column(Text, nullable=True)
    agent_comments = Column(Text, nullable=True)

    # Audit
    audit_primary_status = Column(String, nullable=True)
    audit_secondary_status = Column(String, nullable=True)
    audit_disposition = Column(String, nullable=True)
    audit_comments = Column(Text, nullable=True)

    # Billing
    billing_delivery_status = Column(String, nullable=True)
    billing_packaged_by = Column(String, nullable=True)
    billing_status = Column(String, nullable=True)
    billing_date = Column(Date, nullable=True)

    # Generic columns for 74-column CSV alignment
    col49 = Column(String, nullable=True); col50 = Column(String, nullable=True); col51 = Column(String, nullable=True)
    col52 = Column(String, nullable=True); col53 = Column(String, nullable=True); col54 = Column(String, nullable=True)
    col55 = Column(String, nullable=True); col56 = Column(String, nullable=True); col57 = Column(String, nullable=True)
    col58 = Column(String, nullable=True); col59 = Column(String, nullable=True); col60 = Column(String, nullable=True)
    col61 = Column(String, nullable=True); col62 = Column(String, nullable=True); col63 = Column(String, nullable=True)
    col64 = Column(String, nullable=True); col65 = Column(String, nullable=True); col66 = Column(String, nullable=True)
    col67 = Column(String, nullable=True); col68 = Column(String, nullable=True); col69 = Column(String, nullable=True)
    col70 = Column(String, nullable=True); col71 = Column(String, nullable=True); col72 = Column(String, nullable=True)
    col73 = Column(String, nullable=True); col74 = Column(String, nullable=True)

    # Relationships
    company = relationship("Company")
    job_profile = relationship("JobProfile")
    user_scored_by = relationship("User", foreign_keys=[scored_by])
    user_audit_by = relationship("User", foreign_keys=[audit_by])
    campaign = relationship("Campaign")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    url = Column(String, nullable=True)
    location = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    employee_size = Column(String, nullable=True)
    proof_links = Column(Text, nullable=True)


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="draft")
    order_id = Column(String, nullable=True, unique=True)
    type = Column(String, nullable=True)
    segment = Column(String, nullable=True)
    asset_id = Column(String, nullable=True)
    
    # Original fields to keep existing functionality working
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    target_audience = Column(String, nullable=True)
    budget = Column(Float, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

    creator = relationship("User", foreign_keys=[created_by])
    segments = relationship("CampaignSegment", back_populates="campaign", cascade="all, delete-orphan")


class CampaignSegment(Base):
    __tablename__ = "campaign_segments"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    job_titles = Column(JSONB, default=list)
    industries = Column(JSONB, default=list)
    geos = Column(JSONB, default=list)
    suppression_lists = Column(JSONB, default=list)
    target_company_lists = Column(JSONB, default=list)
    lead_allocation = Column(Integer, nullable=True)

    campaign = relationship("Campaign", back_populates="segments")
    assets = relationship("PromotionalAsset", back_populates="segment", cascade="all, delete-orphan")


class PromotionalAsset(Base):
    __tablename__ = "promotional_assets"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(Integer, ForeignKey("campaign_segments.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)
    url = Column(String, nullable=True)

    segment = relationship("CampaignSegment", back_populates="assets")


class State(Base):
    __tablename__ = "states"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)


class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)


class JobProfile(Base):
    __tablename__ = "job_profiles"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String, nullable=True)
    function = Column(String, nullable=True)
    department = Column(String, nullable=True)

    __table_args__ = (UniqueConstraint('level', 'function', 'department', name='_level_func_dept_uc'),)

class TargetAccountList(Base):
    __tablename__ = "target_account_lists"

    id = Column(Integer, primary_key=True, index=True)
    list_name = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    country = Column(String, nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True)
    segment_id = Column(Integer, ForeignKey("campaign_segments.id", ondelete="CASCADE"), nullable=True)

class SuppressionList(Base):
    __tablename__ = "suppression_lists"

    id = Column(Integer, primary_key=True, index=True)
    list_name = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    country = Column(String, nullable=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True)
    segment_id = Column(Integer, ForeignKey("campaign_segments.id", ondelete="CASCADE"), nullable=True)
