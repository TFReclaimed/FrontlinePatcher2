import argparse
import glob
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import zipfile

WORKSPACE_DIR = "RippedProject"
TEMP_DIR = "Temp"
PRE_PATCHES_DIR = "PrePatches"
PATCHES_DIR = "Patches"
OVERRIDES_DIR = "Overrides"

def find_unity() -> str:
    unity_path = ""

    # TODO: Handle Windows and macOS paths
    if sys.platform == "linux":
        unity_path = os.path.expanduser("~/Unity/Hub/Editor/2022.3.62f3/Editor/Unity")
    else:
        print("[!] ERROR: Unsupported platform.")
        sys.exit(1)

    if not os.path.isfile(unity_path):
        print("[!] ERROR: Unity executable not found. Please install Unity 2022.3.62f3.")
        sys.exit(1)

    return unity_path

def check_prerequisites() -> None:
    missing_tools = False

    if not shutil.which("git"):
        print("[!] ERROR: Git is not installed or not found in PATH.")
        missing_tools = True

    if missing_tools:
        print("[!] Please install the missing tools and ensure they are accessible via the command line.")
        sys.exit(1)
    else:
        print("[+] All prerequisites are met.")

def run_cmd(cmd: list, cwd: str=None, ignore_errors: bool=False) -> None:
    print(f"[*] Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0 and not ignore_errors:
        print(f"[!] ERROR: Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)

def run_assetripper(input_dir: str, output_dir: str) -> None:
    # TODO: Handle Windows and macOS paths
    cmd = [
        "./AssetRipper.GUI.Free",
        "--headless",
        "--log=false",
        "--port=6464"
    ]

    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "1767225600"

    print("[*] Starting AssetRipper in the background...")
    process = subprocess.Popen(cmd, env=env)

    print("[*] Waiting for AssetRipper to start...")

    server_up = False
    for _ in range(10):
        if process.poll() is not None:
            print("[!] ERROR: AssetRipper process terminated unexpectedly.")
            sys.exit(1)

        try:
            urllib.request.urlopen("http://127.0.0.1:6464/", timeout=2)
            server_up = True
            break
        except urllib.error.URLError:
            pass

        time.sleep(1)

    if not server_up:
        print("[!] ERROR: Timed out waiting for AssetRipper to start.")
        process.terminate()
        sys.exit(1)

    print("[*] AssetRipper is running. Proceeding with load and export...")
    print("[*] This may take several minutes. Please wait...")

    try:
        load_data = urllib.parse.urlencode({
            "path": os.path.abspath(input_dir)
        }).encode("utf-8")
        load_req = urllib.request.Request("http://127.0.0.1:6464/LoadFolder", data=load_data, method="POST")
        load_req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(load_req, timeout=1800) as response:
            if response.status == 200:
                print("[+] Load completed successfully!")
            else:
                print(f"[!] ERROR: Load failed with status code {response.status}")
                sys.exit(1)

        print("[*] Starting export... This may take several minutes.")

        export_data = urllib.parse.urlencode({
            "path": os.path.abspath(output_dir)
        }).encode("utf-8")
        export_req = urllib.request.Request("http://127.0.0.1:6464/Export/UnityProject", data=export_data, method="POST")
        export_req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(export_req, timeout=1800) as response:
            if response.status == 200:
                print("[+] Export completed successfully!")
            else:
                print(f"[!] ERROR: Export failed with status code {response.status}")
                sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[!] ERROR: Export request failed: {e}")
        sys.exit(1)
    finally:
        print("[*] Stopping AssetRipper...")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        print("[*] AssetRipper stopped.")

def cmd_setup(apk_path: str, bundles_path: str) -> None:
    check_prerequisites()

    if os.path.exists(WORKSPACE_DIR):
        print(f"[!] ERROR: Workspace directory '{WORKSPACE_DIR}' already exists. Please remove it before running setup.")
        sys.exit(1)

    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)

    os.makedirs(TEMP_DIR, exist_ok=True)

    print("[*] Extracting APK...")
    apk_extract_path = os.path.join(TEMP_DIR, "apk_extracted")
    with zipfile.ZipFile(apk_path, "r") as zip_ref:
        zip_ref.extractall(apk_extract_path)

    print("[*] Copying asset bundles...")
    if not os.path.exists(bundles_path):
        print(f"[!] ERROR: Bundles directory '{bundles_path}' does not exist.")
        sys.exit(1)

    bundles_copy_path = os.path.join(TEMP_DIR, "bundles")
    shutil.copytree(bundles_path, bundles_copy_path)

    print("[*] Running AssetRipper...")
    output_dir = os.path.join(TEMP_DIR, "ripped_project")
    run_assetripper(TEMP_DIR, output_dir)

    print("[*] Moving exported project to workspace...")
    exported_project_path = os.path.join(output_dir, "ExportedProject")
    if not os.path.exists(exported_project_path):
        print(f"[!] ERROR: Expected exported project directory '{exported_project_path}' not found.")
        sys.exit(1)

    shutil.move(exported_project_path, WORKSPACE_DIR)

    print("[*] Copy overrides...")
    overrides_dst = os.path.join(WORKSPACE_DIR, "Assets")
    shutil.copytree(OVERRIDES_DIR, overrides_dst, dirs_exist_ok=True)

    print("[*] Copy gitignore...")
    gitignore_src = os.path.join(os.path.dirname(__file__), "unity.gitignore")
    gitignore_dst = os.path.join(WORKSPACE_DIR, ".gitignore")
    shutil.copyfile(gitignore_src, gitignore_dst)

    print("[*] Initializing Git repository...")
    run_cmd(["git", "init"], cwd=WORKSPACE_DIR)
    run_cmd(["git", "add", "."], cwd=WORKSPACE_DIR)
    run_cmd(["git", "commit", "-m", "AssetRipper", "--author", "TF Reclaimed <auto@mated.null>"], cwd=WORKSPACE_DIR)
    run_cmd(["git", "tag", "raw-project"], cwd=WORKSPACE_DIR)

    pre_patches = sorted(glob.glob(os.path.abspath(os.path.join(PRE_PATCHES_DIR, "*.patch"))))
    if pre_patches:
        print(f"[*] Applying {len(pre_patches)} pre-patches...")
        run_cmd(["git", "am", "--3way"] + pre_patches, cwd=WORKSPACE_DIR)

    print("[*] Upgrading and reserializing Unity project...")
    print("[*] This may take several minutes. Please wait...")

    unity_path = find_unity()
    run_cmd([
        unity_path,
        "-quit",
        "-batchmode",
        "-projectPath",
        os.path.abspath(WORKSPACE_DIR),
        "-executeMethod",
        "AssetTools.ForceReserializeAssets",
        "-logFile",
        os.path.abspath(os.path.join(TEMP_DIR, "unity_upgrade.log"))
    ])

    print("[+] Finished project upgrade!")

    print("[*] Committing upgraded project...")
    run_cmd(["git", "add", "."], cwd=WORKSPACE_DIR)
    run_cmd(["git", "commit", "-m", "Base project", "--author", "TF Reclaimed <auto@mated.null>"], cwd=WORKSPACE_DIR)
    run_cmd(["git", "tag", "base-project"], cwd=WORKSPACE_DIR)

    patches = sorted(glob.glob(os.path.abspath(os.path.join(PATCHES_DIR, "*.patch"))))
    if patches:
        print(f"[*] Applying {len(patches)} patches...")
        run_cmd(["git", "am", "--3way"] + patches, cwd=WORKSPACE_DIR)
    else:
        print("[*] No patches found to apply.")

    print("[*] Deleting temporary files...")
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    shutil.rmtree("temp", ignore_errors=True) # AssetRipper

    print(f"[+] Setup completed successfully! You can now open '{WORKSPACE_DIR}' in Unity.")

def cmd_rebuild() -> None:
    check_prerequisites()

    if not os.path.exists(WORKSPACE_DIR):
        print(f"[!] ERROR: Workspace directory '{WORKSPACE_DIR}' does not exist. Please run 'setup' first.")
        sys.exit(1)

    os.makedirs(PRE_PATCHES_DIR, exist_ok=True)
    os.makedirs(PATCHES_DIR, exist_ok=True)

    print("[*] Rebuilding patches...")
    for patch in glob.glob(os.path.join(PRE_PATCHES_DIR, "*.patch")):
        os.remove(patch)

    for patch in glob.glob(os.path.join(PATCHES_DIR, "*.patch")):
        os.remove(patch)

    export_flags = [
        "--zero-commit",
        "--no-numbered",
        "--no-stat",
        "--no-signature",
        "--unified=1",
        "--minimal"
    ]

    result = subprocess.run(["git", "rev-parse", "--verify", "base-project"], cwd=WORKSPACE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    has_base = (result.returncode == 0)

    if not has_base:
        print("[!] 'base-project' tag not found.")
        print(f"[*] Exporting pre-patches...")
        run_cmd([
            "git",
            "format-patch",
            "raw-project..HEAD",
            "-o",
            os.path.abspath(PRE_PATCHES_DIR)
        ] + export_flags, cwd=WORKSPACE_DIR)

        print("[+] Pre-patches rebuilt successfully.")
        return

    print("[*] Exporting pre-patches...")
    run_cmd([
        "git",
        "format-patch",
        "raw-project..base-project^",
        "-o",
        os.path.abspath(PRE_PATCHES_DIR)
    ] + export_flags, cwd=WORKSPACE_DIR)

    print("[*] Exporting patches...")
    run_cmd([
        "git",
        "format-patch",
        "base-project..HEAD",
        "-o",
        os.path.abspath(PATCHES_DIR)
    ] + export_flags, cwd=WORKSPACE_DIR)

    print(f"[+] Patches rebuilt successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Frontline Patcher")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_setup = subparsers.add_parser("setup", help="Set up the workspace")
    parser_setup.add_argument("apk", help="Path to the game .apk file")
    parser_setup.add_argument("bundles", help="Path to a folder containing the game asset bundles")

    parser_rebuild = subparsers.add_parser("rebuild", help="Rebuild all patches")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args.apk, args.bundles)
    elif args.command == "rebuild":
        cmd_rebuild()