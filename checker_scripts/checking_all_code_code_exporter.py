import os

# Files and Folders to IGNORE (So we don't bloat the file)
IGNORE_DIRS = {
    'node_modules', 'venv', '__pycache__', '.git', '.next', 
    'dist', 'build', 'coverage', '.vscode', '.idea'
}

IGNORE_FILES = {
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 
    'astra.db', '.DS_Store', '.env', '.env.local', 
    'export_code.py', 'full_codebase.txt', 'README.md'
}

# File extensions we actually want to read
ALLOWED_EXTENSIONS = {
    '.ts', '.tsx', '.js', '.jsx', '.py', '.css', '.html', '.json', '.sql'
}

OUTPUT_FILE = "full_codebase.txt"

def is_allowed_file(filename):
    # Check if file is in ignore list
    if filename in IGNORE_FILES:
        return False
    # Check extension
    _, ext = os.path.splitext(filename)
    return ext in ALLOWED_EXTENSIONS

def main():
    root_dir = os.getcwd() # Current directory
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        outfile.write(f"PROJECT DUMP: {os.path.basename(root_dir)}\n")
        outfile.write("="*50 + "\n\n")

        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Modify dirnames in-place to exclude ignored directories
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

            for filename in filenames:
                if is_allowed_file(filename):
                    file_path = os.path.join(dirpath, filename)
                    relative_path = os.path.relpath(file_path, root_dir)

                    try:
                        with open(file_path, "r", encoding="utf-8") as infile:
                            content = infile.read()
                            
                            # Write File Header
                            outfile.write(f"\n{'='*20} START FILE: {relative_path} {'='*20}\n")
                            outfile.write(content)
                            outfile.write(f"\n{'='*20} END FILE: {relative_path} {'='*20}\n\n")
                            
                            print(f"✅ Added: {relative_path}")
                    except Exception as e:
                        print(f"⚠️ Could not read {relative_path}: {e}")

    print(f"\n🎉 Done! All code saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()