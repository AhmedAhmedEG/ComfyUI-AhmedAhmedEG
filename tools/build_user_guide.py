"""Build the current illustrated offline guide."""
try:
    from .build_handbook import build
except ImportError:
    from build_handbook import build

if __name__ == "__main__":
    build()
