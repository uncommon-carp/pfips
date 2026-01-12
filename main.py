import json
from typing import List, Union
from fastapi import Depends, FastAPI, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from db import APIKey, SessionLocal, User, UsageLog
from datetime import datetime, timezone

app = FastAPI()

security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class County(BaseModel):
    county: str
    state: str
    fips: str
    stateAbbrev: str
    fips: str


class SearchInput(BaseModel):
    county: str | None = None
    state: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    name: str


class APIKeyCreate(BaseModel):
    user_id: int
    name: str


#####################################
#               LOGIC               #
#####################################


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> tuple[APIKey, User]:
    """Verify API key from Authorization: Bearer <key> header"""

    api_key = (
        db.query(APIKey)
        .filter(APIKey.key == credentials.credentials, APIKey.is_active)
        .first()
    )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
        )

    user = db.query(User).filter(User.id == api_key.user_id, User.is_active).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is inactive"
        )

    # Update last used timestamp
    api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()

    return api_key, user


async def log_usage(
    request: Request,
    auth_data: tuple[APIKey, User],
    db: Session,
    status_code: int = 200,
):
    """Log API usage"""
    api_key, user = auth_data

    log = UsageLog(
        user_id=user.id,
        api_key_str=api_key.key,
        endpoint=request.url.path,
        method=request.method,
        status_code=status_code,
    )
    db.add(log)
    db.commit()


def normalize_county(county: str, is_louisiana: bool = False) -> str:
    cased = county.upper()
    ends_with_county = cased.endswith(" COUNTY")
    ends_with_parish = cased.endswith(" PARISH")

    if not ends_with_county and not ends_with_parish:
        if is_louisiana:
            return cased.strip() + " PARISH"
        else:
            return cased.strip() + " COUNTY"

    return cased


def get_counties_by_state(state: str) -> Union[List[County], str]:
    print("get_counties_by_state")
    normalized_state = state.upper()
    state_counties = []
    with open("fips_list.json") as file:
        counties = json.load(file)

        for county in counties:
            if county["state"] == normalized_state:
                state_counties.append(county)

    if not state_counties:
        raise HTTPException(status_code=404, detail="No results found")

    return state_counties


def get_counties_by_name(name: str) -> Union[List[County], str]:
    print("get_counties_by_name")
    normalized_county = normalize_county(name)
    state_counties = []
    with open("fips_list.json") as file:
        counties = json.load(file)

        for county in counties:
            if county["county"] == normalized_county:
                state_counties.append(county)

    if not state_counties:
        raise HTTPException(status_code=404, detail="No results found")

    return state_counties


def get_county_by_state_and_name(
    state: str, county_name: str
) -> Union[List[County], str]:
    print("get_county_by_state_and_name")
    if not county_name or not state:
        return "Please provide a county name and state"

    normalized_state = state.upper()
    normalized_county = normalize_county(county_name, state == "LOUSIANA")

    print(normalized_county, normalized_state)

    with open("fips_list.json") as file:
        counties = json.load(file)

        for county in counties:
            if (
                county["state"] == normalized_state
                or county["stateAbbrev"] == normalized_state
            ) and county["county"] == normalized_county:
                return [county]

    raise HTTPException(status_code=404, detail="No results found")


#####################################
#              ROUTES               #
#####################################


@app.get("/api/v2/index")
def get_all_counties() -> List[County]:
    with open("fips_list.json") as file:
        counties = json.load(file)

        all_counties = []

        for county in counties:
            all_counties.append(county)

        return all_counties


@app.get("/api/v2/search")
async def county_search(
    request: Request,
    auth_data: tuple[APIKey, User] = Depends(verify_api_key),
    state: str | None = None,
    county: str | None = None,
    db: Session = Depends(get_db),
):
    print(state, county)
    if not state and not county:
        raise HTTPException(
            status_code=400, detail="Invalid request: missing search parameters"
        )
    elif state and not county:
        await log_usage(request, auth_data, db, 200)
        return get_counties_by_state(state)
    elif county and not state:
        await log_usage(request, auth_data, db, 200)
        return get_counties_by_name(county)
    elif state and county:
        await log_usage(request, auth_data, db, 200)
        return get_county_by_state_and_name(state, county)


@app.post("/admin/users")
async def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    user = User(email=user_data.email, name=user_data.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/admin/api-keys")
async def create_api_key(key_data: APIKeyCreate, db: Session = Depends(get_db)):
    """Create an API key for a user"""
    import secrets

    user = db.query(User).filter(User.id == key_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    key = secrets.token_urlsafe(32)
    api_key = APIKey(key=key, user_id=key_data.user_id, name=key_data.name)
    db.add(api_key)
    db.commit()

    return {"key": key, "user_id": key_data.user_id, "name": key_data.name}


@app.get("/admin/usage/{user_id}")
async def get_usage(user_id: int, db: Session = Depends(get_db)):
    """Get usage stats for a user"""
    logs = db.query(UsageLog).filter(UsageLog.user_id == user_id).all()
    return {"user_id": user_id, "total_requests": len(logs), "logs": logs}
