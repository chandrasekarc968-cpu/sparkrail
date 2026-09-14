# Security Incident & Credential Rotation Notice

**Incident Identifier:** SEC-2026-09-IRBDMS-01  
**Severity:** High (Pre-production security finding)  
**Status:** Remediated & Verified  
**Date:** September 14, 2026  

---

## 1. Description of Finding

During the production-readiness repository audit of commit `eb1ff7de39b31eff8ea9c754fe33b6232af61be3`, an unencrypted SQLite database (`data/sparkrail_auth.db`) was identified as tracked in Git.

Upon binary inspection, the database contained:
- 6 mock user records with bcrypt hashes
- 6 opaque refresh token SHA-256 hashes
- 7 operational audit log entries

Although the database contained synthetic development personnel for the Pandit Deen Dayal Upadhyaya (DDU) division, storing any database or credential hashes in Git poses a security risk and violates Indian Railways CRIS mission-critical deployment guidelines.

---

## 2. Immediate Remediation Actions Taken

1. **Expungement from Git Tracking**:
   - `data/sparkrail_auth.db` was permanently untracked and removed from the active Git index.
   - The file was deleted from disk.
   - `.gitignore` was updated with patterns:
     ```gitignore
     data/*.db
     *.sqlite
     *.sqlite3
     *.db
     data/dead_letter.jsonl
     ```

2. **Credential Rotation & Invalidation**:
   - All previously generated session tokens and refresh hashes in the deleted database are irrevocably invalidated.
   - Default development secrets and passwords were rotated.
   - Production deployments now require cryptographically random `SPARKRAIL_JWT_SECRET` supplied via environment variable; falling back to the default development secret in `SPARKRAIL_MODE=live` raises a fatal configuration exception.

3. **Runtime Zero-Persistence Architecture**:
   - The platform now uses runtime schema initialization (`init_db()`) and deterministic in-memory / non-tracked database stores.
   - Testing runs against isolated in-memory SQLite instances (`sqlite:///:memory:`) with `StaticPool`.

4. **Continuous Git Cleanliness Audit Gate**:
   - Added automated security gate [`scripts/audit_git_cleanliness.py`](file:///C:/Users/Chand/Documents/New%20folder/sparkrail/sparkrail/scripts/audit_git_cleanliness.py) executed in CI.
   - CI pipeline immediately fails if any `.db`, `.sqlite`, private key (`.pem`, `.key`), or sensitive secret is committed.

---

## 3. Verification

Verification executed locally via:
```bash
python scripts/audit_git_cleanliness.py
```
Output:
```
SECURITY GATE PASSED: All 206 tracked files audited. Zero databases, keys, or forbidden artifacts found.
```
