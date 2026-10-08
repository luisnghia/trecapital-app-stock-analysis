"""Synthetic browser Push credentials; tests replace every network provider."""
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def push_keys():
    public = ec.derive_private_key(7, ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    return {"p256dh": encode(public), "auth": encode(b"Q" * 16)}
