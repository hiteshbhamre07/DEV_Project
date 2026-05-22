from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.leads import Lead
from app.security import check_path_permission, get_current_user
from app.models.user import User

router = APIRouter(
    prefix="/crm/api/leads",
    tags=["leads"],
    dependencies=[Depends(check_path_permission)]
)

@router.get("/")
def get_leads(db: Session = Depends(get_db)):
    leads = db.query(Lead).all()
    # Ensure relationships are loaded if using Lazy Loading, 
    # but for a simple API, we can just return the objects if SQLAlchemy handles serialization,
    # or explicitly join if needed for performance/correctness.
    # Given the existing setup, let's just make sure we return what's needed for the UI.
    result = []
    for lead in leads:
        result.append({
            "id": lead.id,
            "name": lead.name,
            "email": lead.email,
            "status": lead.status,
            "company_name": lead.company.name if lead.company else None,
            "campaign_name": lead.campaign.name if lead.campaign else None,
            "created_at": lead.created_at.strftime("%Y-%m-%d %H:%M") if lead.created_at else None
        })
    return result

@router.get("/{lead_id}")
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

@router.post("/", status_code=201)
def create_lead(payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Basic creation logic, can be refined based on schemas if found
    new_lead = Lead(**payload)
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)
    return new_lead

@router.put("/{lead_id}")
def update_lead(lead_id: int, payload: dict, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for var, value in payload.items():
        setattr(lead, var, value)
    db.commit()
    db.refresh(lead)
    return lead

@router.delete("/{lead_id}")
def delete_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return {"detail": "Lead deleted successfully"}