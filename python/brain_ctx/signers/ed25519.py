"""
Ed25519Signer
=============
Cryptographic signing and verification for brain.ctx files.

Uses Ed25519 via PyNaCl (libsodium binding).
Install:  pip install brain-ctx[signing]

Why Ed25519?
- Fast (sub-millisecond sign + verify)
- Small keys (32 bytes public, 64 bytes private)
- Modern — same algorithm GitHub uses for SSH keys
- Deterministic — same content always produces same signature

Usage:
    # Generate a key pair (one time)
    Ed25519Signer.generate_keypair("~/.brain-ctx/")

    # Sign
    ctx.sign("~/.brain-ctx/private.key")
    ctx.save()

    # Verify
    assert ctx.verify_signature()
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brain_ctx.core import BrainCtx


class Ed25519Signer:

    # ── Key generation ─────────────────────────────────────

    @staticmethod
    def generate_keypair(output_dir: str | Path = ".") -> tuple[Path, Path]:
        """
        Generate an Ed25519 key pair and save to disk.

        Args:
            output_dir: Directory to save private.key and public.key

        Returns:
            (private_key_path, public_key_path)

        Example:
            priv, pub = Ed25519Signer.generate_keypair("~/.brain-ctx/")
            print(f"Keys saved to {priv.parent}")
        """
        _require_nacl()
        from nacl.signing import SigningKey

        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)

        sk = SigningKey.generate()
        priv_path = output / "private.key"
        pub_path  = output / "public.key"

        priv_path.write_bytes(bytes(sk))
        pub_path.write_bytes(bytes(sk.verify_key))

        # Set restrictive permissions on private key
        priv_path.chmod(0o600)

        return priv_path, pub_path

    # ── Sign ───────────────────────────────────────────────

    @staticmethod
    def sign(ctx: "BrainCtx", private_key_path: Path) -> dict:
        """
        Sign a BrainCtx and return the signature block.

        The signature covers the canonical JSON of all fields
        except the signature block itself — so the signature
        is deterministic and verifiable.

        Args:
            ctx:              BrainCtx to sign
            private_key_path: Path to Ed25519 private key

        Returns:
            signature dict to set on ctx.signature
        """
        _require_nacl()
        from nacl.signing import SigningKey

        key_bytes = _read_key(private_key_path)
        sk        = SigningKey(key_bytes)

        payload  = _canonical_payload(ctx)
        signed   = sk.sign(payload.encode("utf-8"))
        sig_b64  = base64.b64encode(signed.signature).decode("ascii")
        pub_b64  = base64.b64encode(bytes(sk.verify_key)).decode("ascii")

        return {
            "algorithm":  "ed25519",
            "public_key": pub_b64,
            "value":      sig_b64,
            "signed_at":  datetime.now(timezone.utc).isoformat(),
        }

    # ── Verify ─────────────────────────────────────────────

    @staticmethod
    def verify(ctx: "BrainCtx") -> bool:
        """
        Verify the Ed25519 signature on a BrainCtx.

        Returns True if signature is valid, False otherwise.
        Never raises — returns False on any error.
        """
        # Check signature exists BEFORE requiring nacl
        sig_block = ctx.signature
        if not sig_block or not sig_block.get("value") or not sig_block.get("public_key"):
            return False

        _require_nacl()
        from nacl.signing  import VerifyKey
        from nacl.exceptions import BadSignatureError

        sig_block = ctx.signature
        if not sig_block or not sig_block.get("value") or not sig_block.get("public_key"):
            return False

        try:
            pub_key = VerifyKey(base64.b64decode(sig_block["public_key"]))
            sig     = base64.b64decode(sig_block["value"])
            payload = _canonical_payload(ctx)
            pub_key.verify(payload.encode("utf-8"), sig)
            return True
        except (BadSignatureError, Exception):
            return False

    # ── Fingerprint ────────────────────────────────────────

    @staticmethod
    def fingerprint(ctx: "BrainCtx") -> str | None:
        """
        Return a short human-readable fingerprint of the public key.
        Like SSH key fingerprints — useful for display.

        Returns: "SHA256:xxxx..." or None if unsigned.
        """
        import hashlib
        sig = ctx.signature
        if not sig or not sig.get("public_key"):
            return None
        pub_bytes = base64.b64decode(sig["public_key"])
        digest    = hashlib.sha256(pub_bytes).digest()
        b64       = base64.b64encode(digest).decode("ascii").rstrip("=")
        return f"SHA256:{b64}"


# ── Helpers ────────────────────────────────────────────────────

def _require_nacl() -> None:
    try:
        import nacl  # noqa: F401
    except ImportError:
        raise ImportError(
            "PyNaCl is required for signing. Install with:\n"
            "  pip install brain-ctx[signing]\n"
            "  # or: pip install PyNaCl"
        ) from None


def _read_key(path: Path) -> bytes:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Private key not found: {path}")
    raw = path.read_bytes()
    # Support raw 32-byte keys or base64-encoded keys
    if len(raw) == 32:
        return raw
    try:
        return base64.b64decode(raw.strip())
    except Exception:
        return raw[:32]


def _canonical_payload(ctx: "BrainCtx") -> str:
    """
    Build the canonical string that gets signed.

    Excludes the signature block itself — so signing is
    deterministic and verification doesn't need the sig.
    Fields are sorted for canonical ordering.
    """
    data = ctx.to_dict()
    data.pop("signature", None)  # exclude sig block from payload
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
