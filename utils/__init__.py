import hashlib


def ripemd160(x: bytes) -> bytes:
    try:
        h = hashlib.new("ripemd160")
        h.update(x)
        return h.digest()
    except BaseException:
        # ripemd160 is not always present in hashlib.
        # Fallback to custom implementation if missing.
        from . import ripemd
        return ripemd.ripemd160(x)


def sha256(s: bytes) -> bytes:
    return hashlib.new('sha256', s).digest()


def hash160(s: bytes) -> bytes:
    return ripemd160(sha256(s))


def hash256(s: bytes) -> bytes:
    return sha256(sha256(s))
