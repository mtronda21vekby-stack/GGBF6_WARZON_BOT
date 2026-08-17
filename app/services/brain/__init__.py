# BLACK CROWN OPS v38 ecosystem locale policy.
# Import-time installation is intentional: all BrainEngine/AIHook paths import
# this package before PromptBuilder is instantiated, preserving one language rule.
from app.services.brain.locale_patch import install as _install_locale_policy

_install_locale_policy()
