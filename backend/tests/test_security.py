from app.core.security import get_password_hash, verify_password


def test_password_hashing_and_verification() -> None:
    password = "securepassword123!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert len(hashed) > 20
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_verify_password_handles_invalid_hash() -> None:
    assert verify_password("password", "invalidhash") is False
