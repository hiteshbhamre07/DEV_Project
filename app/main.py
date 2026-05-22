# Triggering reload after schema fix
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List

from app import models, security
from app.database import engine, get_db

# Create the database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="RP_CRM API")

# Serve static files (favicon, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")


from app.schemas.user_schema import Token, UserCreate, RoleCreate, User, Role
from app.routes import admin, crm_auth, leads, mis, crm_dashboard, lists
from app.routes import campaigns as crm_campaigns_router

from fastapi.responses import RedirectResponse

app.include_router(admin.router)
app.include_router(crm_auth.router)
app.include_router(leads.router)
app.include_router(mis.router)
app.include_router(crm_dashboard.router)
app.include_router(crm_campaigns_router.router)
app.include_router(lists.router)

@app.get("/")
def root_redirect():
    return RedirectResponse(url="/crm/auth/login")


from app.security import check_path_permission

@app.get("/admin/api/app-paths", dependencies=[Depends(check_path_permission)])
def get_app_paths():
    """Return all unique route paths registered in the app — powers the path dropdown in Permissions UI."""
    paths = set()
    for route in app.routes:
        if hasattr(route, "path"):
            p = route.path
            # Skip internal/utility paths
            if p in ("/", "/token", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"):
                continue
            if "{" in p:
                # For parameterised routes, use the prefix before the param
                prefix = p[:p.index("{")].rstrip("/")
                if prefix:
                    paths.add(prefix)
            else:
                paths.add(p.rstrip("/") or "/")
    return sorted(paths)


from fastapi.responses import JSONResponse

@app.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    # Authenticate user by email (using username field in OAuth2 form)
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create JWT
    access_token_expires = security.timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    # Create a JSONResponse to attach the cookie to
    is_admin = user.role.is_admin if user.role else False
    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer", "is_admin": is_admin})
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True,
        max_age=security.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return response


@app.post("/users/", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Encrypt the password
    hashed_password = security.get_password_hash(user.password)
    new_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        role_id=user.role_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/roles/", response_model=Role, status_code=status.HTTP_201_CREATED)
def create_role(role: RoleCreate, db: Session = Depends(get_db)):
    db_role = db.query(models.Role).filter(models.Role.name == role.name).first()
    if db_role:
        raise HTTPException(status_code=400, detail="Role name already exists")
    
    new_role = models.Role(
        name=role.name,
        job_role=role.job_role,
        department=role.department,
        is_admin=role.is_admin
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role


@app.get("/users/me/", response_model=User)
def read_users_me(current_user: models.User = Depends(security.get_current_user)):
    return current_user
