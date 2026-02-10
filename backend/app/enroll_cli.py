"""
Enrollment CLI for Wedding Face Forward.

Simple command-line interface to enroll users via selfie.

Usage:
    python -m app.enroll_cli <selfie_path> <user_name> [--phone PHONE] [--email EMAIL]

Examples:
    python -m app.enroll_cli selfie.jpg "John Doe"
    python -m app.enroll_cli selfie.jpg "Jane Smith" --phone "+1234567890" --email "jane@email.com"
"""

import argparse
import logging
import sys
from pathlib import Path

from .config import get_config
from .db import get_db
from .enrollment import enroll_user, get_enrollment_status


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Enroll a user by matching their selfie to event photos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "selfie",
        type=Path,
        help="Path to selfie image"
    )
    
    parser.add_argument(
        "name",
        type=str,
        help="User's display name (e.g., 'John Doe')"
    )
    
    parser.add_argument(
        "--phone",
        type=str,
        default=None,
        help="User's phone number"
    )
    
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="User's email address"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show enrollment status and exit"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup
    setup_logging("DEBUG" if args.verbose else "INFO")
    config = get_config()
    config.ensure_directories()
    
    # Initialize database
    db = get_db()
    
    # Show status if requested
    if args.status:
        status = get_enrollment_status()
        print("\n=== Enrollment Status ===")
        print(f"Total Persons Detected: {status['total_persons']}")
        print(f"Total Enrolled: {status['total_enrolled']}")
        print(f"Pending Enrollment: {status['pending_enrollment']}")
        
        if status['enrollments']:
            print("\n--- Enrolled Users ---")
            for e in status['enrollments']:
                print(f"  • {e['user_name']} (Person ID: {e['person_id']}, Confidence: {e['confidence']})")
        return 0
    
    # Validate selfie path
    if not args.selfie.exists():
        print(f"Error: Selfie file not found: {args.selfie}")
        return 1
    
    # Perform enrollment
    print(f"\n🎯 Enrolling '{args.name}' using selfie: {args.selfie}")
    print("-" * 50)
    
    result = enroll_user(
        selfie_path=args.selfie,
        user_name=args.name,
        phone=args.phone,
        email=args.email
    )
    
    # Display result
    print()
    if result.success:
        print("✅ ENROLLMENT SUCCESSFUL!")
        print(f"   Person ID: {result.person_id}")
        print(f"   Folder Name: {result.person_name}")
        print(f"   Match Confidence: {result.match_confidence:.1%}")
        if result.solo_folder:
            print(f"   Solo Photos: {result.solo_folder}")
        if result.group_folder:
            print(f"   Group Photos: {result.group_folder}")
    else:
        print("❌ ENROLLMENT FAILED")
        print(f"   Reason: {result.message}")
        if result.match_confidence > 0:
            print(f"   Best Match Confidence: {result.match_confidence:.1%}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
