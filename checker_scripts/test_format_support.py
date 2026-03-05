"""
Quick test to verify AVIF, WebP, and HEIC support is working.
"""
from PIL import Image
import sys

def test_format_support():
    """Test if PIL can handle modern formats."""
    
    print("Testing modern image format support...")
    print("=" * 50)
    
    # Test WebP
    try:
        from PIL import WebPImagePlugin
        print("[OK] WebP: Supported (native)")
    except ImportError:
        print("[FAIL] WebP: Not supported")
    
    # Test AVIF
    try:
        from pillow_avif import AvifImagePlugin
        print("[OK] AVIF: Supported (pillow-avif-plugin)")
    except ImportError:
        print("[FAIL] AVIF: Not supported (install: pip install pillow-avif-plugin)")
    
    # Test HEIC/HEIF
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        print("[OK] HEIC/HEIF: Supported (pillow-heif)")
    except ImportError:
        print("[FAIL] HEIC/HEIF: Not supported (install: pip install pillow-heif)")
    
    print("=" * 50)
    print(f"PIL Version: {Image.__version__}")
    print(f"Supported formats: {', '.join(sorted(Image.registered_extensions().keys()))}")

if __name__ == "__main__":
    test_format_support()
