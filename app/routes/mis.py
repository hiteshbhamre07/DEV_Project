from fastapi import APIRouter, Depends
from app.security import check_path_permission

router = APIRouter(
    prefix="/crm/mis",
    tags=["mis"],
    dependencies=[Depends(check_path_permission)]
)

@router.get("/")
def get_mis():
    return {"message": "MIS accessed"}
