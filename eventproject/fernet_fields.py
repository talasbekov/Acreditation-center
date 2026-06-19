from django.utils import encoding


if not hasattr(encoding, "force_text"):
    encoding.force_text = encoding.force_str

from fernet_fields import EncryptedCharField

__all__ = ["EncryptedCharField"]
