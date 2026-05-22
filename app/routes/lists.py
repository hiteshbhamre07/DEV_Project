from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.database import engine, get_db
from app.models.leads import TargetAccountList, SuppressionList, CampaignSegment
from app.security import get_current_user
from app.models.user import User
import shutil
import os
import csv
from fastapi.responses import JSONResponse

router = APIRouter(
    prefix="/crm/api/lists",
    tags=["lists"]
)

@router.get("/tal")
def get_tal_lists(campaign_id: int = None, segment_id: int = None, db: Session = Depends(get_db)):
    query = db.query(TargetAccountList.list_name).distinct()
    if campaign_id:
        query = query.filter(TargetAccountList.campaign_id == campaign_id)
    if segment_id:
        query = query.filter(TargetAccountList.segment_id == segment_id)
    lists = query.all()
    return [l[0] for l in lists]

@router.get("/suppression")
def get_suppression_lists(campaign_id: int = None, segment_id: int = None, db: Session = Depends(get_db)):
    query = db.query(SuppressionList.list_name).distinct()
    if campaign_id:
        query = query.filter(SuppressionList.campaign_id == campaign_id)
    if segment_id:
        query = query.filter(SuppressionList.segment_id == segment_id)
    lists = query.all()
    return [l[0] for l in lists]

@router.post("/upload")
def upload_list_csv(
    list_type: str = Form(...), # 'tal' or 'suppression'
    list_name: str = Form(...),
    file: UploadFile = File(...),
    campaign_id: str = Form(None),
    segment_id: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if list_type not in ["tal", "suppression"]:
        raise HTTPException(status_code=400, detail="Invalid list_type. Must be 'tal' or 'suppression'.")

    if not list_name.strip():
        raise HTTPException(status_code=400, detail="List name is required.")

    # Convert NA to None, parse ints
    if campaign_id == "NA": campaign_id = None
    elif campaign_id: campaign_id = int(campaign_id)
    
    if segment_id == "NA": segment_id = None
    elif segment_id: segment_id = int(segment_id)

    temp_file_path = f"temp_{file.filename}"
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        raw_conn = engine.raw_connection()
        try:
            cursor = raw_conn.cursor()
            
            # Create a temp table to load the csv
            cursor.execute("DROP TABLE IF EXISTS temp_list_load;")
            cursor.execute("""
                CREATE TEMPORARY TABLE temp_list_load (
                    company_name VARCHAR,
                    domain VARCHAR,
                    country VARCHAR,
                    campaign_id INTEGER,
                    segment_id INTEGER
                );
            """)
            
            # Load CSV into temp table safely by reading and filtering columns
            import io
            
            with open(temp_file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
                reader = csv.DictReader(f)
                headers = [h.strip().lower() for h in (reader.fieldnames or [])]
                
                # Check for required columns (allow some flexibility)
                # Map expected fields
                company_col = next((h for h in headers if 'company' in h and 'name' in h), 'company_name' if 'company_name' in headers else None)
                domain_col = next((h for h in headers if 'domain' in h), 'domain' if 'domain' in headers else None)
                country_col = next((h for h in headers if 'country' in h), 'country' if 'country' in headers else None)
                
                # We will write strict data to a buffer and COPY from that
                buffer = io.StringIO()
                writer = csv.writer(buffer)
                writer.writerow(['company_name', 'domain', 'country', 'campaign_id', 'segment_id'])
                
                for row in reader:
                    # Clean up keys for matching
                    clean_row = {k.strip().lower(): v for k, v in row.items() if k}
                    
                    c_val = clean_row.get(company_col, '') if company_col else ''
                    d_val = clean_row.get(domain_col, '') if domain_col else ''
                    ctry_val = clean_row.get(country_col, '') if country_col else ''
                    
                    if c_val or d_val: # Only insert if at least company or domain is present
                        writer.writerow([c_val, d_val, ctry_val, campaign_id or '', segment_id or ''])
                        
                buffer.seek(0)
                
            cursor.copy_expert("COPY temp_list_load (company_name, domain, country, campaign_id, segment_id) FROM STDIN WITH CSV HEADER", buffer)

            target_table = "target_account_lists" if list_type == "tal" else "suppression_lists"

            # Auto-migrate if columns don't exist
            try:
                cursor.execute(f"ALTER TABLE {target_table} ADD COLUMN IF NOT EXISTS campaign_id INTEGER;")
                cursor.execute(f"ALTER TABLE {target_table} ADD COLUMN IF NOT EXISTS segment_id INTEGER;")
            except Exception as e:
                print(f"Migration error (ignoring): {e}")

            # Insert into the actual table
            insert_query = f"""
                INSERT INTO {target_table} (list_name, company_name, domain, country, campaign_id, segment_id)
                SELECT %s, company_name, domain, country, campaign_id, segment_id
                FROM temp_list_load
            """
            cursor.execute(insert_query, (list_name,))
            
            cursor.execute("SELECT count(*) FROM temp_list_load")
            total_rows = cursor.fetchone()[0]

            # If segment_id is provided, link this list to the segment
            if segment_id:
                segment = db.query(CampaignSegment).filter(CampaignSegment.id == segment_id).first()
                if segment:
                    # Initialize lists if None
                    if segment.target_company_lists is None:
                        segment.target_company_lists = []
                    if segment.suppression_lists is None:
                        segment.suppression_lists = []
                        
                    # Create a new list based on current JSONB value
                    if list_type == "tal":
                        current_lists = list(segment.target_company_lists)
                        if list_name not in current_lists:
                            current_lists.append(list_name)
                            segment.target_company_lists = current_lists
                    elif list_type == "suppression":
                        current_lists = list(segment.suppression_lists)
                        if list_name not in current_lists:
                            current_lists.append(list_name)
                            segment.suppression_lists = current_lists
                    
                    db.add(segment)

            db.commit() # commit sqlalchemy changes
            raw_conn.commit() # commit raw psycopg2 changes
            return {"message": f"Successfully uploaded {total_rows} records to {list_name}", "rows": total_rows}
        except Exception as e:
            raw_conn.rollback()
            print(f"Error executing list upload: {e}")
            raise HTTPException(status_code=500, detail=f"Database error during upload: {str(e)}")
        finally:
            raw_conn.close()

    except Exception as e:
        print(f"Error during list upload: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        except Exception as e:
            print(f"Cleanup error: {e}")
