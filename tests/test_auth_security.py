import hashlib
import json

import main_app


def test_admin_login_requires_explicit_env_var(monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert main_app.authenticate("admin", "admin123") is None


def test_admin_login_works_when_env_var_is_set(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "secure-pass")
    auth = main_app.authenticate("admin", "secure-pass")
    assert auth
    assert auth["role"] == "admin"


def test_user_login_supports_pbkdf2_password_hash(monkeypatch, tmp_path):
    users_file = tmp_path / "users.json"
    password = "p@ssw0rd!"
    salt = "unit-test-salt"
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    ).hex()
    users_file.write_text(
        json.dumps(
            {
                "users": {
                    "alice": {
                        "password_hash": f"pbkdf2_sha256$100000${salt}${digest}",
                        "role": "user",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main_app, "USERS_FILE", str(users_file))

    assert main_app.authenticate("alice", password)["role"] == "user"
    assert main_app.authenticate("alice", "wrong-password") is None
