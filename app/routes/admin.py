from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.database import get_db
from app.models.user import User, Role, Permission
from app.schemas.user_schema import (
    User as UserSchema, 
    UserCreate, 
    UserUpdate, 
    UserStatusUpdate,
    PasswordChange,
    Role as RoleSchema,
    RoleCreate,
    RoleUpdate
)
from app.schemas.permission_schema import (
    Permission as PermissionSchema,
    PermissionCreate,
    PermissionUpdate,
    RolePermissionAssign
)
from app.security import get_current_user, get_password_hash

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

# --- Page Routes (HTML) ---

@router.get("/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
def admin_dashboard(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_count = db.query(User).count()
    role_count = db.query(Role).count()
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, 
        "user_count": user_count, 
        "role_count": role_count,
        "current_user": current_user
    })

@router.get("/users", response_class=HTMLResponse)
def admin_users_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "current_user": current_user
    })

@router.get("/roles", response_class=HTMLResponse)
def admin_roles_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    return templates.TemplateResponse("admin/roles.html", {
        "request": request,
        "current_user": current_user
    })

@router.get("/permissions", response_class=HTMLResponse)
def admin_permissions_page(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    return templates.TemplateResponse("admin/permissions.html", {
        "request": request,
        "current_user": current_user
    })

# --- JSON API Endpoints ---

# User Management APIs

@router.get("/api/users", response_model=List[UserSchema])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(User).all()

@router.post("/api/users", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    user_in: UserCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_user = db.query(User).filter(User.email == user_in.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=hashed_password,
        role_id=user_in.role_id,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.put("/api/users/{user_id}", response_model=UserSchema)
def update_user_endpoint(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/api/users/{user_id}/status", response_model=UserSchema)
def toggle_user_status(
    user_id: int,
    status_in: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.is_active = status_in.is_active
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/api/users/{user_id}/password")
def change_user_password(
    user_id: int,
    pw_in: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.hashed_password = get_password_hash(pw_in.new_password)
    db.commit()
    return {"detail": "Password updated successfully"}

@router.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_endpoint(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    return None

# Role Management APIs

@router.get("/api/roles", response_model=List[RoleSchema])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Role).all()

@router.post("/api/roles", response_model=RoleSchema, status_code=status.HTTP_201_CREATED)
def create_role_endpoint(
    role_in: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_role = db.query(Role).filter(Role.name == role_in.name).first()
    if db_role:
        raise HTTPException(status_code=400, detail="Role name already exists")
    
    new_role = Role(
        name=role_in.name,
        job_role=role_in.job_role,
        department=role_in.department,
        is_admin=role_in.is_admin
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role

@router.put("/api/roles/{role_id}", response_model=RoleSchema)
def update_role_endpoint(
    role_id: int,
    role_in: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_role = db.query(Role).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    update_data = role_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_role, field, value)
    
    db.commit()
    db.refresh(db_role)
    return db_role

@router.delete("/api/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role_endpoint(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_role = db.query(Role).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Preventing deletion of roles with active users
    user_count = db.query(User).filter(User.role_id == role_id).count()
    if user_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete role with assigned users")
    
    db.delete(db_role)
    db.commit()
    return None

# Permission Management APIs

@router.get("/api/permissions", response_model=List[PermissionSchema])
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Permission).all()

@router.post("/api/permissions", response_model=PermissionSchema, status_code=status.HTTP_201_CREATED)
def create_permission(
    perm_in: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_perm = db.query(Permission).filter(Permission.name == perm_in.name).first()
    if db_perm:
        raise HTTPException(status_code=400, detail="Permission name already exists")
    
    new_perm = Permission(name=perm_in.name, path=perm_in.path)
    db.add(new_perm)
    db.commit()
    db.refresh(new_perm)
    return new_perm

@router.put("/api/permissions/{perm_id}", response_model=PermissionSchema)
def update_permission(
    perm_id: int,
    perm_in: PermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_perm = db.query(Permission).filter(Permission.id == perm_id).first()
    if not db_perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    update_data = perm_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_perm, field, value)
    
    db.commit()
    db.refresh(db_perm)
    return db_perm

@router.delete("/api/permissions/{perm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permission(
    perm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_perm = db.query(Permission).filter(Permission.id == perm_id).first()
    if not db_perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    db.delete(db_perm)
    db.commit()
    return None

@router.get("/api/roles/{role_id}/permissions", response_model=List[PermissionSchema])
def list_role_permissions(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_role = db.query(Role).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    return db_role.permissions

@router.put("/api/roles/{role_id}/permissions", status_code=status.HTTP_204_NO_CONTENT)
def update_role_permissions(
    role_id: int,
    assign_in: RolePermissionAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_role = db.query(Role).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    perms = db.query(Permission).filter(Permission.id.in_(assign_in.permission_ids)).all()
    db_role.permissions = perms
    db.commit()
    return None