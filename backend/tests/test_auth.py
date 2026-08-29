import pytest
from app.auth import hash_password, verify_password, create_access_token, decode_access_token

def test_password_hashing_and_verification():
    raw_pass = "VocalisSecurePass2026!"
    hashed = hash_password(raw_pass)
    
    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False

def test_jwt_token_generation_and_decoding():
    business_id = "bus_test_12345"
    token = create_access_token(business_id)
    
    assert isinstance(token, str)
    assert len(token) > 20
    
    decoded_id = decode_access_token(token)
    assert decoded_id == business_id

def test_jwt_invalid_token():
    invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"
    assert decode_access_token(invalid_token) is None
