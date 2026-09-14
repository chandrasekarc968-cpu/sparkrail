import time
import pytest
from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.models import (
    Base,
    UserTable,
    RefreshTokenTable,
    AuditLogTable,
    Role,
    Department,
    ROLE_CAPABILITIES
)
from src.auth.database import get_db
from src.auth.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    decode_access_token,
    issue_refresh_token,
    rotate_refresh_token,
    revoke_token,
    require_auth,
    require_role,
    require_department,
    require_division,
    AUTH_RATE_LIMITER
)
from src.auth.audit import log_audit_event, verify_audit_log_chain
from src.auth.routes import router as auth_router
from src.auth.seeder import seed_default_users, DEFAULT_PASSWORD
from src.api.main import app


# -----------------------------------------------------------------------------
# TEST FIXTURES WITH ISOLATED IN-MEMORY SQLALCHEMY DATABASE
# -----------------------------------------------------------------------------

from sqlalchemy.pool import StaticPool

@pytest.fixture(scope="module")
def test_db_engine():
    """Isolated in-memory SQLite engine for tests using StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    with sessionmaker(autocommit=False, autoflush=False, bind=engine)() as db:
        seed_default_users(db, DEFAULT_PASSWORD)
    return engine


@pytest.fixture(scope="module")
def TestSessionLocal(test_db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)


@pytest.fixture(scope="module")
def seeded_db(TestSessionLocal):
    db = TestSessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="module")
def client(test_db_engine, TestSessionLocal):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# -----------------------------------------------------------------------------
# STEP 2 & 3: UNIT TESTS FOR PASSWORD SECURITY & DOMAIN MODELS
# -----------------------------------------------------------------------------

def test_password_strength_policy():
    """Enforces minimum 10 chars, uppercase, lowercase, digit, and special char."""
    valid, err = validate_password_strength("Short1!")
    assert not valid
    assert "at least 10" in err

    valid, err = validate_password_strength("alllowercase123!")
    assert not valid
    assert "uppercase" in err

    valid, err = validate_password_strength("ALLUPPERCASE123!")
    assert not valid
    assert "lowercase" in err

    valid, err = validate_password_strength("NoDigitsSpecial!")
    assert not valid
    assert "digit" in err

    valid, err = validate_password_strength("NoSpecialChar123")
    assert not valid
    assert "special character" in err

    valid, err = validate_password_strength("RailOps@2026!")
    assert valid
    assert err is None


def test_bcrypt_hashing_and_verification():
    """Verifies adaptive bcrypt work factor 12 hashing and comparison."""
    password = "SecureRailPassword#2026"
    hashed = hash_password(password)
    assert hashed != password
    assert hashed.startswith("$2b$12$")  # Confirms cost factor 12
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword123!", hashed)


# -----------------------------------------------------------------------------
# STEP 4: INTEGRATION TESTS FOR AUTHENTICATION ENDPOINTS
# -----------------------------------------------------------------------------

def test_successful_login_with_email_and_pf_number(client, seeded_db):
    """Test login via email and via PF number returns access & refresh tokens."""
    # 1. Login via email (SR_DOM)
    res_email = client.post("/api/v1/auth/login", json={
        "identifier": "srdom.ddu@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    assert res_email.status_code == 200, res_email.text
    data_email = res_email.json()
    assert "access_token" in data_email
    assert "refresh_token" in data_email
    assert data_email["user"]["role"] == "SR_DOM"
    assert data_email["user"]["department"] == "OPERATING"
    assert data_email["user"]["division_code"] == "ECR-DDU"
    assert "SANCTION_BLOCK" in data_email["user"]["capabilities"]

    # 2. Login via PF Number (CTPC)
    res_pf = client.post("/api/v1/auth/login", json={
        "identifier": "PF-ECR-90802",
        "password": DEFAULT_PASSWORD
    })
    assert res_pf.status_code == 200, res_pf.text
    data_pf = res_pf.json()
    assert data_pf["user"]["email"] == "ctpc.ddu@indianrailways.gov.in"
    assert data_pf["user"]["role"] == "CTPC"
    assert "APPROVE_OHE_ISOLATION" in data_pf["user"]["capabilities"]


def test_login_invalid_credentials(client):
    """Rejects wrong passwords and unknown identifiers with 401."""
    res = client.post("/api/v1/auth/login", json={
        "identifier": "srdom.ddu@indianrailways.gov.in",
        "password": "IncorrectPassword!999"
    })
    assert res.status_code == 401
    assert "Invalid" in res.json()["detail"]

    res_unknown = client.post("/api/v1/auth/login", json={
        "identifier": "unknown.officer@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    assert res_unknown.status_code == 401


def test_rate_limiting_brute_force_protection(client):
    """Ensures max 5 failed attempts per 15 minutes triggers HTTP 429 Too Many Requests."""
    target_id = "brute.force@indianrailways.gov.in"
    AUTH_RATE_LIMITER.reset()

    # 5 failed attempts
    for i in range(5):
        res = client.post("/api/v1/auth/login", json={
            "identifier": target_id,
            "password": f"WrongAttempt#{i}!"
        })
        assert res.status_code == 401

    # 6th attempt should be blocked by rate limiter
    res_blocked = client.post("/api/v1/auth/login", json={
        "identifier": target_id,
        "password": "AnyPassword!2026"
    })
    assert res_blocked.status_code == 429
    assert "Too many failed login attempts" in res_blocked.json()["detail"]

    # Reset for subsequent tests
    AUTH_RATE_LIMITER.reset()


def test_me_endpoint_and_claims(client):
    """GET /api/v1/auth/me returns current user profile and capabilities."""
    login_res = client.post("/api/v1/auth/login", json={
        "identifier": "sse.pway.ddu@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    token = login_res.json()["access_token"]

    # Valid token
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    user_info = me_res.json()
    assert user_info["role"] == "SSE_PWAY"
    assert user_info["department"] == "CIVIL"
    assert "REQUEST_CIVIL_BLOCK" in user_info["capabilities"]

    # Missing token
    res_no_auth = client.get("/api/v1/auth/me")
    assert res_no_auth.status_code == 401

    # Malformed token
    res_bad_token = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
    assert res_bad_token.status_code == 401


def test_token_refresh_and_rotation(client, seeded_db):
    """POST /api/v1/auth/refresh rotates the refresh token and invalidates the previous one."""
    login_res = client.post("/api/v1/auth/login", json={
        "identifier": "sm.ddu@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    old_refresh = login_res.json()["refresh_token"]

    # First refresh
    ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert ref_res.status_code == 200
    ref_data = ref_res.json()
    new_access = ref_data["access_token"]
    new_refresh = ref_data["refresh_token"]

    assert new_access != login_res.json()["access_token"]
    assert new_refresh != old_refresh

    # Replaying old refresh token must be rejected
    replay_res = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay_res.status_code == 401
    assert "revoked" in replay_res.json()["detail"].lower()


def test_logout_revokes_token(client):
    """POST /api/v1/auth/logout revokes active refresh token."""
    login_res = client.post("/api/v1/auth/login", json={
        "identifier": "sse.sig.ddu@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    refresh_token = login_res.json()["refresh_token"]

    # Logout
    logout_res = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_res.status_code == 200
    assert "revoked" in logout_res.json()["message"].lower()

    # Attempting to refresh with logged-out token fails
    refresh_attempt = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_attempt.status_code == 401


# -----------------------------------------------------------------------------
# STEP 4: RBAC ROUTE GUARDS & DIVISION MULTI-TENANCY TESTS
# -----------------------------------------------------------------------------

# Define test endpoint with explicit RBAC role guards
rbac_test_app = FastAPI()

@rbac_test_app.post("/test/ctpc-isolation")
def approve_power_isolation(current_user: UserTable = Depends(require_role([Role.CTPC]))):
    return {"status": "Power isolation sanctioned", "approver": current_user.pf_number}

@rbac_test_app.post("/test/civil-block-request")
def request_civil_block(current_user: UserTable = Depends(require_role([Role.SSE_PWAY]))):
    return {"status": "Civil block request submitted", "approver": current_user.pf_number}

@rbac_test_app.post("/test/operating-dept-only")
def operating_action(current_user: UserTable = Depends(require_department([Department.OPERATING]))):
    return {"status": "Operating department cleared", "user": current_user.email}

@rbac_test_app.post("/test/division-guard/{division_code}")
def division_guarded_action(division_code: str, current_user: UserTable = Depends(require_auth)):
    require_division(division_code, current_user)
    return {"status": "Division authorized", "division": division_code}


@pytest.fixture(scope="module")
def rbac_client(TestSessionLocal):
    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    rbac_test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(rbac_test_app) as c:
        yield c
    rbac_test_app.dependency_overrides.clear()


def test_rbac_sse_pway_forbidden_from_ctpc_power_block(client, rbac_client):
    """
    CRITICAL REQUIREMENT: Verify that SSE_PWAY receives HTTP 403 Forbidden
    when attempting to approve a CTPC power shut-off.
    """
    # 1. Login as SSE_PWAY
    pway_login = client.post("/api/v1/auth/login", json={
        "identifier": "sse.pway.ddu@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    pway_token = pway_login.json()["access_token"]

    # 2. Attempt CTPC power isolation
    res_forbidden = rbac_client.post(
        "/test/ctpc-isolation",
        headers={"Authorization": f"Bearer {pway_token}"}
    )
    assert res_forbidden.status_code == 403
    assert "Operation requires role in ['CTPC']" in res_forbidden.json()["detail"]

    # 3. Login as CTPC and verify success
    ctpc_login = client.post("/api/v1/auth/login", json={
        "identifier": "ctpc.ddu@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    ctpc_token = ctpc_login.json()["access_token"]

    res_allowed = rbac_client.post(
        "/test/ctpc-isolation",
        headers={"Authorization": f"Bearer {ctpc_token}"}
    )
    assert res_allowed.status_code == 200
    assert res_allowed.json()["status"] == "Power isolation sanctioned"


def test_department_guard_enforcement(client, rbac_client):
    """Verify require_department enforces departmental boundaries."""
    # CTPC is in TRD department -> should fail OPERATING
    ctpc_login = client.post("/api/v1/auth/login", json={
        "identifier": "ctpc.ddu@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    ctpc_token = ctpc_login.json()["access_token"]

    res = rbac_client.post("/test/operating-dept-only", headers={"Authorization": f"Bearer {ctpc_token}"})
    assert res.status_code == 403
    assert "restricted to departments ['OPERATING']" in res.json()["detail"]

    # SR_DOM is in OPERATING department -> should pass
    srdom_login = client.post("/api/v1/auth/login", json={
        "identifier": "srdom.ddu@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    srdom_token = srdom_login.json()["access_token"]

    res_ok = rbac_client.post("/test/operating-dept-only", headers={"Authorization": f"Bearer {srdom_token}"})
    assert res_ok.status_code == 200


def test_division_multitenancy_guard(client, rbac_client):
    """Verify cross-division actions are forbidden (e.g. DDU officer cannot modify DLI corridor)."""
    ddu_login = client.post("/api/v1/auth/login", json={
        "identifier": "srdom.ddu@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    ddu_token = ddu_login.json()["access_token"]

    # Modifying own division: ECR-DDU
    res_ddu = rbac_client.post("/test/division-guard/ECR-DDU", headers={"Authorization": f"Bearer {ddu_token}"})
    assert res_ddu.status_code == 200

    # Modifying foreign division: NR-DLI -> 403 Forbidden
    res_dli = rbac_client.post("/test/division-guard/NR-DLI", headers={"Authorization": f"Bearer {ddu_token}"})
    assert res_dli.status_code == 403
    assert "Cross-division access violation" in res_dli.json()["detail"]

    # System Admin (CRIS) with division="ALL" -> permitted across all divisions
    admin_login = client.post("/api/v1/auth/login", json={
        "identifier": "admin.cris@indianrailways.gov.in",
        "password": DEFAULT_PASSWORD
    })
    admin_token = admin_login.json()["access_token"]

    res_admin = rbac_client.post("/test/division-guard/NR-DLI", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200


# -----------------------------------------------------------------------------
# STEP 5: AUDIT LOGGING & TAMPER EVIDENCE TESTS
# -----------------------------------------------------------------------------

def test_tamper_evident_audit_logging(seeded_db):
    """
    Verifies that operational actions create chained AuditLog records
    and that cryptographic hash integrity verification detects any tampering.
    """
    user = seeded_db.query(UserTable).filter(UserTable.role == Role.SR_DOM).first()

    # Log 3 sequential actions
    e1 = log_audit_event(
        db=seeded_db,
        action="SANCTION_BLOCK",
        resource_type="TRACK_BLOCK",
        resource_id="BLK-ECR-101",
        user=user,
        metadata_diff={"status": "SANCTIONED", "line": "UP_MAIN"}
    )
    e2 = log_audit_event(
        db=seeded_db,
        action="GENERATE_PRIVATE_NUMBER",
        resource_type="STATION_REGISTER",
        resource_id="PN-4892",
        user=user,
        metadata_diff={"private_number": "PN-4892"}
    )
    e3 = log_audit_event(
        db=seeded_db,
        action="GRANT_BLOCK",
        resource_type="TRACK_BLOCK",
        resource_id="BLK-ECR-101",
        user=user,
        metadata_diff={"granted_duration_minutes": 180}
    )

    assert e2.previous_hash == e1.current_hash
    assert e3.previous_hash == e2.current_hash

    # Verify uncorrupted chain integrity
    is_valid, err = verify_audit_log_chain(seeded_db)
    assert is_valid
    assert err is None

    # Intentionally tamper with an intermediate event to prove fraud detection
    original_action = e2.action
    e2.action = "FRAUDULENT_UNAUTHORIZED_OVERRIDE"
    seeded_db.commit()

    is_valid_tampered, tampered_err = verify_audit_log_chain(seeded_db)
    assert not is_valid_tampered
    assert "Tampered hash" in tampered_err

    # Restore original for cleanliness
    e2.action = original_action
    seeded_db.commit()
