from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.security import get_current_user, check_path_permission, SECRET_KEY, ALGORITHM
from app.models.user import User
from app.models.leads import Campaign, CampaignSegment, PromotionalAsset, Lead
from app.schemas.campaign_schema import CampaignCreate, CampaignUpdate
from app.database import get_db

router = APIRouter(prefix="/crm", tags=["crm-campaigns"])
templates = Jinja2Templates(directory="app/templates")


# ─── Helper: read cookie/header and get user (for page routes) ────────────────

def _user_from_request(request: Request, db: Session) -> User | None:
    from jose import jwt, JWTError
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
    else:
        cookie_val = request.cookies.get("access_token", "")
        token = cookie_val[7:] if cookie_val.lower().startswith("bearer ") else (cookie_val or None)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            return None
    except JWTError:
        return None
    return db.query(User).filter(User.email == email).first()


def _has_path_access(user: User, path: str) -> bool:
    """Same logic as check_path_permission, but returns bool."""
    if user.role and user.role.is_admin:
        return True
    if not user.role or not user.role.permissions:
        return False
    for perm in user.role.permissions:
        if path.startswith(perm.path):
            return True
    return False


# ─── PAGE ROUTE ───────────────────────────────────────────────────────────────

@router.get("/campaigns")
def campaigns_page(request: Request, db: Session = Depends(get_db)):
    user = _user_from_request(request, db)
    if not user:
        return RedirectResponse(url="/crm/auth/login", status_code=302)
    if not _has_path_access(user, "/crm/campaigns"):
        return templates.TemplateResponse("crm/access_denied.html", {
            "request": request, "current_user": user
        }, status_code=403)
    return templates.TemplateResponse("crm/campaigns.html", {
        "request": request, "current_user": user
    })


# ─── API ROUTES (use check_path_permission — fully dynamic RBAC) ──────────────

@router.get("/api/campaigns", dependencies=[Depends(check_path_permission)])
def get_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).all()
    campaign_list = [
        {
            "id": c.id, "name": c.name, "description": c.description,
            "status": c.status, 
            "start_date": c.start_date.strftime('%Y-%m-%d') if c.start_date else None, 
            "end_date": c.end_date.strftime('%Y-%m-%d') if c.end_date else None,
            "target_audience": c.target_audience,
            "budget": c.budget,
            "created_at": c.created_at.strftime('%Y-%m-%d %H:%M:%S') if c.created_at else None, 
            "is_active": c.is_active,
            "segments": [
                {
                    "id": s.id, "name": s.name, "job_titles": s.job_titles,
                    "industries": s.industries, "geos": s.geos, "lead_allocation": s.lead_allocation,
                    "assets": [{"name": a.name, "type": a.type, "url": a.url} for a in s.assets]
                }
                for s in c.segments
            ]
        }
        for c in campaigns
    ]
    if campaign_list:
        print(f"DEBUG CAMPAIGN 0: {campaign_list[0]}")
    return campaign_list


@router.post("/api/campaigns", status_code=201, dependencies=[Depends(check_path_permission)])
def create_campaign(
    payload: CampaignCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if payload.segments and not (current_user.role and current_user.role.is_admin):
        raise HTTPException(status_code=403, detail="Only Admins can configure campaign segments and rules.")
        
    campaign_data = payload.dict(exclude={"segments"})
    campaign = Campaign(**campaign_data, created_by=current_user.id)
    db.add(campaign)
    db.flush() # To get campaign.id
    
    if payload.segments:
        for seg in payload.segments:
            segment_data = seg.dict(exclude={"assets"})
            segment = CampaignSegment(**segment_data, campaign_id=campaign.id)
            db.add(segment)
            db.flush()
            
            if seg.assets:
                for asset in seg.assets:
                    asset_db = PromotionalAsset(**asset.dict(), segment_id=segment.id)
                    db.add(asset_db)
                    
    db.commit()
    db.refresh(campaign)
    return {"id": campaign.id, "name": campaign.name}


@router.put("/api/campaigns/{campaign_id}", dependencies=[Depends(check_path_permission)])
def update_campaign(campaign_id: int, payload: CampaignUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    # Example logic if we updated segments in PUT. For now just update campaign fields.
    for field, value in payload.dict(exclude_unset=True).items():
        if field == "segments":
            continue
        setattr(campaign, field, value)
        
    if payload.segments is not None:
        if not (current_user.role and current_user.role.is_admin):
            raise HTTPException(status_code=403, detail="Only Admins can configure campaign segments and rules.")
        
        payload_seg_ids = [s.id for s in payload.segments if s.id]
        
        for existing_seg in list(campaign.segments):
            if existing_seg.id not in payload_seg_ids:
                db.delete(existing_seg)
                
        for seg_data in payload.segments:
            if seg_data.id:
                existing_seg = db.query(CampaignSegment).filter(CampaignSegment.id == seg_data.id).first()
                if existing_seg:
                    existing_seg.name = seg_data.name
                    existing_seg.job_titles = seg_data.job_titles
                    existing_seg.industries = seg_data.industries
                    existing_seg.geos = seg_data.geos
                    existing_seg.lead_allocation = seg_data.lead_allocation
                    
                    for a in existing_seg.assets:
                        db.delete(a)
                    db.flush()
                    if seg_data.assets:
                        for asset in seg_data.assets:
                            asset_db = PromotionalAsset(**asset.dict(), segment_id=existing_seg.id)
                            db.add(asset_db)
            else:
                new_seg_data = seg_data.dict(exclude={"assets", "id"})
                new_segment = CampaignSegment(**new_seg_data, campaign_id=campaign.id)
                db.add(new_segment)
                db.flush()
                if seg_data.assets:
                    for asset in seg_data.assets:
                        asset_db = PromotionalAsset(**asset.dict(), segment_id=new_segment.id)
                        db.add(asset_db)

    db.commit()
    db.refresh(campaign)
    return {"id": campaign.id, "name": campaign.name}


@router.delete("/api/campaigns/{campaign_id}", dependencies=[Depends(check_path_permission)])
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"detail": "Campaign deleted successfully"}


@router.get("/api/campaigns/{campaign_id}/segments", dependencies=[Depends(check_path_permission)])
def get_campaign_segments(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    segments = db.query(CampaignSegment).filter(CampaignSegment.campaign_id == campaign_id).all()
    return [{"id": s.id, "name": s.name} for s in segments]


@router.get("/api/campaigns/{campaign_id}/segments/{segment_id}/filter-leads", dependencies=[Depends(check_path_permission)])
def filter_segment_leads(campaign_id: int, segment_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import cast, String
    segment = db.query(CampaignSegment).filter(CampaignSegment.id == segment_id, CampaignSegment.campaign_id == campaign_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
        
    query = db.query(Lead)
    
    # Very basic JSONB array intersection logic using OR for demo purposes:
    # Normally we'd use postgres native @> or JSONB operators
    
    # 1. Filter by geos (if specified) -> match Lead.colXX or similar depending on where location is stored
    # Using company_location as a proxy
    if segment.geos:
        geo_filters = [Lead.company_location.ilike(f"%{g}%") for g in segment.geos]
        from sqlalchemy import or_
        query = query.filter(or_(*geo_filters))
        
    # 2. Exclude Target Companies
    if segment.suppression_lists:
        for exc in segment.suppression_lists:
            query = query.filter(Lead.company_name.notilike(f"%{exc}%"))
            
    filtered_leads = query.all()
    
    return {
        "segment": segment.name,
        "matched_leads_count": len(filtered_leads),
        "leads": [{"id": l.id, "email": l.email, "company": l.company_name} for l in filtered_leads]
    }
