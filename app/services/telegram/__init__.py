# -*- coding: utf-8 -*-
from app.services.telegram.console_i18n import install as _install_console_i18n

_install_console_i18n()

from app.services.telegram.command_console import CommandConsoleController
from app.services.telegram.aaa_surface import install as _install_aaa_surface

_install_aaa_surface()

__all__ = ["CommandConsoleController"]
