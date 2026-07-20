"""Registry of all available Samsat adapters."""
from .jakarta import JakartaAdapter
from .jabar import JabarAdapter
from .jatim import JatimAdapter
from .jateng import JatengAdapter
from .banten import BantenAdapter
from .diy import DIYAdapter
from .bali import BaliAdapter

ADAPTERS: dict = {
    "jakarta": JakartaAdapter(),
    "jabar":   JabarAdapter(),
    "jatim":   JatimAdapter(),
    "jateng":  JatengAdapter(),
    "banten":  BantenAdapter(),
    "diy":     DIYAdapter(),
    "bali":    BaliAdapter(),
}

__all__ = ["ADAPTERS"]
