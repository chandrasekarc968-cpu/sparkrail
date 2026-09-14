from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Cookie
from sqlalchemy.orm import Session

from src.auth.database import get_db
from src.auth.models import (
    UserTable,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
    ROLE_CAPABILITIES,
    Role
)
from src.auth.security import (
    verify_password,
    create_access_token,
    issue_refresh_token,
    rotate_refresh_token,
    revoke_token,
    require_auth,
    AUTH_RATE_LIMITER,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from src.auth.audit import log_audit_event

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & RBAC"])


def extract_client_ip(request: Request) -> Optional[str]:
    """Helper to extract real client IP considering forward headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def user_to_response(user: UserTable) -> UserResponse:
    """Formats UserTable ORM model into UserResponse with operational capabilities."""
    user_role = user.role
    if isinstance(user_role, str):
        try:
            user_role = Role(user_role)
        except ValueError:
            user_role = Role.SECTION_CONTROLLER

    caps = ROLE_CAPABILITIES.get(user_role, [])
    return UserResponse(
        id=str(user.id),
        pf_number=user.pf_number,
        email=user.email,
        full_name=user.full_name,
        department=user.department,
        role=user.role,
        division_code=user.division_code,
        zone_code=user.zone_code,
        is_active=user.is_active,
        last_login=user.last_login,
        capabilities=caps
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Authenticates Indian Railways personnel by Provident Fund (PF) number or official email.
    Enforces brute-force rate-limiting, issues short-lived JWT access token and rotatable refresh token.
    """
    client_ip = extract_client_ip(request)
    identifier = payload.identifier.strip()

    # Brute-force rate limiting check (5 attempts / 15 mins)
    is_limited, lock_seconds = AUTH_RATE_LIMITER.is_rate_limited(identifier, client_ip)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Terminal locked for {lock_seconds} seconds."
        )

    # Lookup user by email or PF number (case-insensitive)
    user = db.query(UserTable).filter(
        (UserTable.email.ilike(identifier)) | (UserTable.pf_number.ilike(identifier))
    ).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        AUTH_RATE_LIMITER.record_failure(identifier, client_ip)
        log_audit_event(
            db=db,
            action="FAILED_LOGIN_ATTEMPT",
            resource_type="IDENTITY",
            resource_id=identifier,
            ip_address=client_ip,
            metadata_diff={"identifier": identifier, "reason": "Invalid credentials"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Provident Fund number, email, or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact CRIS Administrator."
        )

    # Reset rate limiting counter on success
    AUTH_RATE_LIMITER.record_success(identifier, client_ip)

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    # Generate tokens
    access_token = create_access_token(user)
    raw_refresh_token = issue_refresh_token(db, user)

    # Set HTTP-only secure cookie for refresh token
    response.set_cookie(
        key="sparkrail_refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=False,  # Set False for localhost development compatibility
        samesite="lax",
        max_age=7 * 24 * 3600
    )

    # Audit log login event
    log_audit_event(
        db=db,
        action="LOGIN",
        resource_type="USER_SESSION",
        resource_id=str(user.id),
        user=user,
        ip_address=client_ip,
        metadata_diff={"role": str(user.role), "division": user.division_code}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_to_response(user)
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token_endpoint(
    request: Request,
    response: Response,
    payload: Optional[RefreshTokenRequest] = None,
    sparkrail_refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """
    Validates the refresh token, performs cryptographic token rotation, and issues a fresh access token.
    """
    raw_token = (payload.refresh_token if payload and payload.refresh_token else None) or sparkrail_refresh_token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token required in request body or cookie"
        )

    client_ip = extract_client_ip(request)
    user, new_raw_token = rotate_refresh_token(db, raw_token)

    new_access_token = create_access_token(user)

    # Update cookie with rotated token
    response.set_cookie(
        key="sparkrail_refresh_token",
        value=new_raw_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 3600
    )

    log_audit_event(
        db=db,
        action="TOKEN_ROTATED",
        resource_type="USER_SESSION",
        resource_id=str(user.id),
        user=user,
        ip_address=client_ip
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_raw_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_to_response(user)
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    payload: Optional[RefreshTokenRequest] = None,
    sparkrail_refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """
    Invalidates the active refresh token in the database and clears auth cookies.
    """
    raw_token = (payload.refresh_token if payload and payload.refresh_token else None) or sparkrail_refresh_token
    client_ip = extract_client_ip(request)

    if raw_token:
        revoke_token(db, raw_token)

    response.delete_cookie(key="sparkrail_refresh_token")

    log_audit_event(
        db=db,
        action="LOGOUT",
        resource_type="USER_SESSION",
        resource_id="SESSION",
        ip_address=client_ip
    )

    return {"message": "Logged out successfully. Tokens revoked."}


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: UserTable = Depends(require_auth)
):
    """
    Returns the authenticated user's profile, operational jurisdiction, and explicit capability list.
    """
    return user_to_response(current_user)
