"""Evidence-grounded CV tailoring and career intelligence workflow."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tailoring-ats-cvs")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["__version__"]
