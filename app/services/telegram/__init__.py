# -*- coding: utf-8 -*-
from app.services.telegram.runtime_compat import (
    install_controller_compatibility as _install_controller_compatibility,
    install_locale_compatibility as _install_locale_compatibility,
)

_install_locale_compatibility()

from app.services.telegram.console_i18n import install as _install_console_i18n

_install_console_i18n()

from app.services.telegram.command_console import CommandConsoleController

_install_controller_compatibility()

from app.services.telegram.aaa_surface import install as _install_aaa_surface

_install_aaa_surface()

__all__ = ["CommandConsoleController"]
