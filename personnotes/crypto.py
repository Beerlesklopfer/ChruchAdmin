"""AES-256-GCM Verschluesselung fuer Seelsorge-Notizen.

Schluessel-Ableitung:
- Wenn settings.NOTES_ENCRYPTION_KEY (32 Bytes base64) gesetzt ist, wird dieser verwendet.
- Sonst wird PBKDF2-SHA256 mit settings.SECRET_KEY und festem Salt verwendet
  (weniger sicher, aber sofort einsatzbereit; SECRET_KEY-Rotation = Datenverlust).
"""
import base64
import os
import logging

from django.conf import settings
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

_KDF_SALT = b'ChurchAdmin-PersonNotes-v1'
_NONCE_SIZE = 12  # GCM-Standard


def _get_key():
    """Liefert 32-Byte AES-Key, entweder aus Settings oder abgeleitet von SECRET_KEY."""
    cfg = getattr(settings, 'NOTES_ENCRYPTION_KEY', None)
    if cfg:
        key = base64.b64decode(cfg)
        if len(key) != 32:
            raise ValueError('NOTES_ENCRYPTION_KEY muss 32 Byte (base64) sein.')
        return key
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_KDF_SALT, iterations=200_000)
    return kdf.derive(settings.SECRET_KEY.encode('utf-8'))


def encrypt(plaintext: str) -> str:
    """Verschluesselt String, gibt base64-Token zurueck (nonce || ciphertext)."""
    if plaintext is None:
        return ''
    aesgcm = AESGCM(_get_key())
    nonce = os.urandom(_NONCE_SIZE)
    ct = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    return base64.b64encode(nonce + ct).decode('ascii')


def decrypt(token: str) -> str:
    """Entschluesselt das base64-Token, gibt Klartext zurueck."""
    if not token:
        return ''
    raw = base64.b64decode(token)
    nonce, ct = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
    aesgcm = AESGCM(_get_key())
    return aesgcm.decrypt(nonce, ct, None).decode('utf-8')
