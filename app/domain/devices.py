from enum import Enum


class Device(str, Enum):
    KBM = "kbm"          # PC mouse+keyboard
    PAD = "pad"          # Controller PS/Xbox
