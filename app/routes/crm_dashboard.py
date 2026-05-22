from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from app.security import get_current_user
from app.models.user import User

from sqlalchemy.orm import Session
from app.database import get_db
from app.models.leads import Lead, Campaign
from app.utils.bulk_upload import fast_load_csv
import os
import shutil
from fastapi import UploadFile, File
from fastapi.responses import RedirectResponse

router = APIRouter(
    prefix="/crm",
    tags=["crm"]
)

templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard")
def get_dashboard(
    request: Request, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total_campaigns = db.query(Campaign).count()
    total_leads = db.query(Lead).count()
    processed_leads = db.query(Lead).filter(Lead.status == "processed").count()
    pending_leads = db.query(Lead).filter(Lead.status == "pending").count()

    return templates.TemplateResponse("crm/dashboard.html", {
        "request": request, 
        "current_user": current_user,
        "total_campaigns": total_campaigns,
        "total_leads": total_leads,
        "processed_leads": processed_leads,
        "pending_leads": pending_leads
    })

@router.get("/leads")
def leads_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    return templates.TemplateResponse("crm/leads.html", {
        "request": request,
        "current_user": current_user
    })

# Kept for backward compatibility if needed, but redirects to /leads
@router.get("/upload")
def upload_redirect():
    return RedirectResponse(url="/crm/leads")

@router.post("/upload")
def upload_leads_post(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    # Save the uploaded file temporarily
    temp_file_path = f"temp_{file.filename}"
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Call the fast_load_csv utility
        rows_imported = fast_load_csv(temp_file_path)
        
        return {"rows": rows_imported}
    except Exception as e:
        print(f"Error during bulk upload: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        # Cleanup temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
