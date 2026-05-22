from app.database import Base
from .user import User, Role, Permission
from .leads import Lead, Company, Campaign, State, Country, JobProfile, TargetAccountList, SuppressionList

# Importing models here ensures they are registered with SQLAlchemy's Base metadata 
# when models.Base is called in main.py
