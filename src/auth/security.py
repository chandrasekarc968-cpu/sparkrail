import os
import re
import time
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union

import bcrypt
import jwt
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.orm import Session

from src.auth.models import (
    UserTable,
    RefreshTokenTable,
    Role,
    Department,
    ROLE_CAPABILITIES
)
from src.auth.database import get_db

# Cryptographic and JWT Configuration
JWT_SECRET_KEY = os.getenv("SPARKRAIL_JWT_SECRET", "sparkrail-ir-mission-critical-auth-secret-key-2026")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
BCRYPT_ROUNDS = 12

# Password policy regex
PASSWORD_MIN_LENGTH = 10
PASSWORD_REGEX_UPPER = re.compile(r"[A-Z]")
PASSWORD_REGEX_LOWER = re.compile(r"[a-z]")
PASSWORD_REGEX_DIGIT = re.compile(r"[0-9]")
PASSWORD_REGEX_SPECIAL = re.compile(r"[!@#$%^&*(),.?\":{}|<>]")


# -----------------------------------------------------------------------------
# PASSWORD SECURITY & COMPLEXITY VALIDATION
# -----------------------------------------------------------------------------

def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Enforces mission-critical password policy:
    - Minimum 10 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
    if not PASSWORD_REGEX_UPPER.search(password):
        return False, "Password must contain at least one uppercase letter"
    if not PASSWORD_REGEX_LOWER.search(password):
        return False, "Password must contain at least one lowercase letter"
    if not PASSWORD_REGEX_DIGIT.search(password):
        return False, "Password must contain at least one numerical digit"
    if not PASSWORD_REGEX_SPECIAL.search(password):
        return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
    return True, None


def hash_password(password: str) -> str:
    """Hashes password using bcrypt with adaptive work factor 12+."""
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against hashed password."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# -----------------------------------------------------------------------------
# TOKEN LIFECYCLE & ROTATION
# -----------------------------------------------------------------------------

def create_access_token(user: UserTable, expires_delta: Optional[timedelta] = None) -> str:
    """
    Issues short-lived JWT access token (15-30 mins) with user claims.
    Claims include sub, pf_number, email, role, department, division_code, zone_code.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    dept_str = user.department.value if hasattr(user.department, "value") else str(user.department)

    payload: Dict[str, Any] = {
        "sub": str(user.id),
        "pf_number": user.pf_number,
        "email": user.email,
        "role": role_str,
        "department": dept_str,
        "division_code": user.division_code,
        "zone_code": user.zone_code,
        "jti": secrets.token_hex(16),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates signature and expiration of JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"}
        )


def generate_opaque_refresh_token() -> str:
    """Generates a cryptographically secure 64-byte random URL-safe string."""
    return secrets.token_urlsafe(64)


def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hash of token for secure database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_refresh_token(db: Session, user: UserTable) -> str:
    """Creates a new refresh token, hashes it, saves in database, and returns the raw token."""
    raw_token = generate_opaque_refresh_token()
    token_h = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    token_record = RefreshTokenTable(
        user_id=user.id,
        token_hash=token_h,
        expires_at=expires_at,
        is_revoked=False
    )
    db.add(token_record)
    db.commit()
    return raw_token


def rotate_refresh_token(db: Session, raw_token: str) -> Tuple[UserTable, str]:
    """
    Validates the refresh token, performs token rotation:
    - Revokes the existing token
    - Issues a fresh refresh token
    - Returns (user, new_raw_token)
    """
    token_h = hash_token(raw_token)
    token_record = db.query(RefreshTokenTable).filter(RefreshTokenTable.token_hash == token_h).first()

    if not token_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if token_record.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")
    
    now = datetime.now(timezone.utc)
    # Ensure expires_at is timezone-aware
    exp = token_record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        token_record.is_revoked = True
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired")

    user = db.query(UserTable).filter(UserTable.id == token_record.user_id, UserTable.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Issue replacement token and link for rotation tracking
    new_raw_token = generate_opaque_refresh_token()
    new_token_h = hash_token(new_raw_token)
    new_expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    token_record.is_revoked = True
    token_record.replaced_by_token_hash = new_token_h

    new_token_record = RefreshTokenTable(
        user_id=user.id,
        token_hash=new_token_h,
        expires_at=new_expires_at,
        is_revoked=False
    )
    db.add(new_token_record)
    db.commit()

    return user, new_raw_token


def revoke_token(db: Session, raw_token: str) -> bool:
    """Revokes active refresh token in database on logout."""
    token_h = hash_token(raw_token)
    token_record = db.query(RefreshTokenTable).filter(RefreshTokenTable.token_hash == token_h).first()
    if token_record:
        token_record.is_revoked = True
        db.commit()
        return True
    return False


# -----------------------------------------------------------------------------
# BRUTE-FORCE PROTECTION & RATE LIMITER
# -----------------------------------------------------------------------------

class InMemoryRateLimiter:
    """
    Sliding window rate limiter: max 5 failed attempts per 15 minutes per IP or user identifier.
    """
    def __init__(self, max_attempts: int = 5, window_seconds: int = 900):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.failed_attempts: Dict[str, List[float]] = {}

    def _cleanup_old_attempts(self, key: str, current_time: float) -> List[float]:
        cutoff = current_time - self.window_seconds
        attempts = [t for t in self.failed_attempts.get(key, []) if t > cutoff]
        self.failed_attempts[key] = attempts
        return attempts

    def is_rate_limited(self, identifier: str, ip_address: Optional[str] = None) -> Tuple[bool, int]:
        """
        Returns (is_limited, seconds_remaining_in_lockout).
        Checks both identifier and IP.
        """
        now = time.time()
        keys_to_check = [f"id:{identifier.lower()}"]
        if ip_address:
            keys_to_check.append(f"ip:{ip_address}")

        for key in keys_to_check:
            attempts = self._cleanup_old_attempts(key, now)
            if len(attempts) >= self.max_attempts:
                oldest_in_window = min(attempts)
                remaining = int(self.window_seconds - (now - oldest_in_window))
                return True, max(remaining, 1)
        return False, 0

    def record_failure(self, identifier: str, ip_address: Optional[str] = None) -> None:
        """Records a failed authentication attempt."""
        now = time.time()
        keys = [f"id:{identifier.lower()}"]
        if ip_address:
            keys.append(f"ip:{ip_address}")

        for key in keys:
            if key not in self.failed_attempts:
                self.failed_attempts[key] = []
            self.failed_attempts[key].append(now)

    def record_success(self, identifier: str, ip_address: Optional[str] = None) -> None:
        """Resets failed attempt counters upon successful authentication."""
        self.failed_attempts.pop(f"id:{identifier.lower()}", None)
        if ip_address:
            self.failed_attempts.pop(f"ip:{ip_address}", None)

    def reset(self) -> None:
        """Clears all tracking records (primarily for testing)."""
        self.failed_attempts.clear()


AUTH_RATE_LIMITER = InMemoryRateLimiter(max_attempts=5, window_seconds=900)


# -----------------------------------------------------------------------------
# ROUTE GUARD MIDDLEWARE & DEPENDENCIES
# -----------------------------------------------------------------------------

def require_auth(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> UserTable:
    """
    Route guard validating Bearer JWT.
    Retrieves user from database and verifies active status.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must start with 'Bearer '",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = authorization[len("Bearer "):].strip()
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")

    user = db.query(UserTable).filter(UserTable.id == user_id, UserTable.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is deactivated or deleted")

    return user


def require_role(roles: List[Union[Role, str]]):
    """
    Factory dependency verifying caller possesses one of the required railway roles.
    Raises HTTP 403 Forbidden on authorization failure.
    """
    allowed_values = {r.value if hasattr(r, "value") else str(r) for r in roles}

    def role_checker(current_user: UserTable = Depends(require_auth)) -> UserTable:
        user_role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        # SYSTEM_ADMIN inherently bypasses operational role constraints
        if user_role_val == Role.SYSTEM_ADMIN.value:
            return current_user

        if user_role_val not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires role in {sorted(list(allowed_values))}. Current role: '{user_role_val}'"
            )
        return current_user

    return role_checker


def require_department(departments: List[Union[Department, str]]):
    """
    Factory dependency verifying caller is in one of the required railway departments.
    Raises HTTP 403 Forbidden on authorization failure.
    """
    allowed_depts = {d.value if hasattr(d, "value") else str(d) for d in departments}

    def dept_checker(current_user: UserTable = Depends(require_auth)) -> UserTable:
        user_dept_val = current_user.department.value if hasattr(current_user.department, "value") else str(current_user.department)
        # SYSTEM_ADMIN / ADMIN inherently bypasses departmental isolation
        if user_dept_val == Department.ADMIN.value or current_user.role == Role.SYSTEM_ADMIN:
            return current_user

        if user_dept_val not in allowed_depts:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation restricted to departments {sorted(list(allowed_depts))}. Current department: '{user_dept_val}'"
            )
        return current_user

    return dept_checker


def require_division(resource_division_code: str, user: UserTable) -> None:
    """
    Enforces multi-tenancy boundaries across railway divisions.
    Prevents a controller from DLI modifying possessions in DDU.
    Raises HTTP 403 Forbidden if division mismatch.
    """
    if user.division_code == "ALL" or user.role == Role.SYSTEM_ADMIN:
        return

    # Normalize comparison
    u_div = user.division_code.strip().upper()
    r_div = resource_division_code.strip().upper()

    # Match exact or prefix (e.g., "ECR-DDU" vs "DDU")
    if u_div != r_div and not u_div.endswith(r_div) and not r_div.endswith(u_div):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-division access violation: User division '{user.division_code}' cannot modify resources in division '{resource_division_code}'"
        )
