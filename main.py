# -*- coding: utf-8 -*-
import os
import sys

# ✅ гарантируем, что корень проекта в sys.path (Render-safe)
sys.path.insert(0, os.path.dirname(__file__))

from app.runner import main

if __name__ == "__main__":
    main()
