"""Live HTTP test verifying end-to-end authentication, JWT issuance, RBAC, and error responses."""

import sys
import threading
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import requests
import uvicorn
from app.main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")

def main():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)

    base = "http://127.0.0.1:8001"
    print("--- 1. Testing Health Endpoint ---")
    r = requests.get(f"{base}/health", timeout=5)
    print("Health check response:", r.status_code, r.json())
    assert r.status_code == 200

    print("\n--- 2. Testing Demo Role Logins ---")
    roles = [
        ("Admin", "admin@enterprise.com"),
        ("Manager", "manager@enterprise.com"),
        ("HR User", "hr@enterprise.com"),
        ("Employee", "employee@enterprise.com"),
        ("Freelancer", "freelancer2@test.com"),
        ("Admin (.local)", "admin@enterprise.local"),
        ("Manager (.local)", "manager@enterprise.local"),
        ("HR (.local)", "hr@enterprise.local"),
        ("Employee (.local)", "employee@enterprise.local"),
    ]
    tokens = {}
    for role_name, email in roles:
        res = requests.post(
            f"{base}/api/v1/auth/login",
            json={"email": email, "password": "Admin@123"},
            timeout=5,
        )
        print(f"[SUCCESS] {role_name} ({email}) -> Status: {res.status_code}")
        assert res.status_code == 200, f"Failed for {email}: {res.text}"
        data = res.json()
        assert "access_token" in data
        assert data["user"]["email"] == email
        tokens[email] = data["access_token"]
        print(f"          Logged in as: {data['user']['email']} | Role: {data['user']['role']}")

    print("\n--- 3. Testing Protected Endpoint (/auth/me) ---")
    for email, token in tokens.items():
        me_res = requests.get(
            f"{base}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        assert me_res.status_code == 200
        print(f"[VERIFIED] /auth/me for {email}: role={me_res.json()['role']}")

    print("\n--- 4. Testing Invalid Password ---")
    bad_pw = requests.post(
        f"{base}/api/v1/auth/login",
        json={"email": "admin@enterprise.com", "password": "WrongPassword!"},
        timeout=5,
    )
    print("[VERIFIED] Invalid password -> Status:", bad_pw.status_code, bad_pw.json())
    assert bad_pw.status_code == 401
    assert bad_pw.json()["detail"] == "Invalid email or password."

    print("\n--- 5. Testing Invalid Email ---")
    bad_email = requests.post(
        f"{base}/api/v1/auth/login",
        json={"email": "nonexistent@test.com", "password": "Admin@123"},
        timeout=5,
    )
    print("[VERIFIED] Non-existent email -> Status:", bad_email.status_code, bad_email.json())
    assert bad_email.status_code == 401
    assert bad_email.json()["detail"] == "Invalid email or password."

    bad_fmt = requests.post(
        f"{base}/api/v1/auth/login",
        json={"email": "not-an-email", "password": "Admin@123"},
        timeout=5,
    )
    print("[VERIFIED] Malformed email format -> Status:", bad_fmt.status_code)
    assert bad_fmt.status_code == 422

    print("\n--- 6. Testing RBAC Access Control ---")
    admin_token = tokens["admin@enterprise.com"]
    manager_token = tokens["manager@enterprise.com"]
    employee_token = tokens["employee@enterprise.com"]

    # Admin can provision new users
    adm_res = requests.post(
        f"{base}/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "sub.worker@enterprise.com", "password": "SecurePassword123!", "role": "Employee"},
        timeout=5,
    )
    print("[VERIFIED] Admin creating user -> Status:", adm_res.status_code)
    assert adm_res.status_code == 201

    # Manager is forbidden from provisioning users (403)
    mgr_res = requests.post(
        f"{base}/api/v1/auth/users",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"email": "illegal.mgr@enterprise.com", "password": "SecurePassword123!", "role": "Employee"},
        timeout=5,
    )
    print("[VERIFIED] Manager attempting user creation -> Status:", mgr_res.status_code, mgr_res.json()["detail"])
    assert mgr_res.status_code == 403

    # Employee is forbidden from provisioning users (403)
    emp_res = requests.post(
        f"{base}/api/v1/auth/users",
        headers={"Authorization": f"Bearer {employee_token}"},
        json={"email": "illegal.emp@enterprise.com", "password": "SecurePassword123!", "role": "Employee"},
        timeout=5,
    )
    print("[VERIFIED] Employee attempting user creation -> Status:", emp_res.status_code, emp_res.json()["detail"])
    assert emp_res.status_code == 403

    print("\n=======================================================")
    print("  ALL 6 LIVE HTTP AUTHENTICATION TESTS PASSED 100%!   ")
    print("=======================================================")

if __name__ == "__main__":
    main()

