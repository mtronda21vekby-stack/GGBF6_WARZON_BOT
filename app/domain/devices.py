from enum import Enum


class Device(str, Enum):
    KBM = "kbm"           # PC Mouse & Keyboard
    CONTROLLER = "pad"    # PS / Xbox
