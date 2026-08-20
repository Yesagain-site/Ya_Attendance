"""
Known device profile for the ZKTeco terminal we are targeting.

Filled in from the on-screen Device Info / Firmware Info panels so the
discovery tool can positively identify OUR unit among any other ZK
devices that might answer on the network.
"""

# --- Identity (from Device Info screen) ---
DEVICE_NAME = "Horus TL2"
SERIAL_NUMBER = "CQRT231060212"
MAC_ADDRESS = "00:17:61:10:b8:0b"
PLATFORM = "ZMM510_TFT"
FACE_ALGORITHM = "ZKFace VX3.5"
MANUFACTURER = "ZKTECO CO., LTD."

# --- Firmware (from Firmware Info screen) ---
FIRMWARE_VERSION = "ZMM510-NF-Ver1.0.21"
PUSH_SERVICE = "2.0.33S"   # ADMS / HTTP push supported
DEV_SERVICE = "2.0.1"      # standard SDK service on TCP 4370

# --- Connection ---
# Standard ZKTeco SDK service port. TCP is the default; some units only
# answer over UDP. The discovery tool tries TCP first, then UDP.
SDK_PORT = 4370
