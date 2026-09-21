import ctypes
from ctypes import wintypes


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


try:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
except Exception:
    crypt32 = None

CRYPTPROTECT_UI_FORBIDDEN = 0x01


def protect_data(data: bytes) -> bytes:
    if not data or not crypt32:
        return b""

    in_buffer = ctypes.create_string_buffer(data)
    blob_in = DATA_BLOB(len(data), in_buffer)
    blob_out = DATA_BLOB()

    if crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(blob_out),
    ):
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)

    raise ValueError("CryptProtectData failed")


def unprotect_data(data: bytes) -> bytes:
    if not data or not crypt32:
        return b""

    in_buffer = ctypes.create_string_buffer(data)
    blob_in = DATA_BLOB(len(data), in_buffer)
    blob_out = DATA_BLOB()

    if crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(blob_out),
    ):
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)

    raise ValueError("CryptUnprotectData failed")
