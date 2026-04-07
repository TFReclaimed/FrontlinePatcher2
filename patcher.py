import argparse
import collections
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import zipfile

import yaml

sys.stdout.reconfigure(line_buffering=True)

WORKSPACE_DIR = "RippedProject"
TEMP_DIR = "Temp"
PRE_PATCHES_DIR = "PrePatches"
PATCHES_DIR = "Patches"
OVERRIDES_DIR = "Overrides"

def find_unity() -> list:
    unity_version = "2022.3.62f3"
    unity_path = ""

    if "CI" in os.environ:
        return [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{os.getcwd()}:{os.getcwd()}",
            "-w",
            os.getcwd(),
            f"unityci/editor:ubuntu-{unity_version}-linux-il2cpp-3",
            "unity-editor"
        ]
    elif sys.platform == "linux":
        unity_path = os.path.expanduser(f"~/Unity/Hub/Editor/{unity_version}/Editor/Unity")
    elif sys.platform == "darwin":
        unity_path = f"/Applications/Unity/Hub/Editor/{unity_version}/Unity.app/Contents/MacOS/Unity"
    elif sys.platform == "win32":
        unity_path = f"C:/Program Files/Unity/Hub/Editor/{unity_version}/Editor/Unity.exe"
    else:
        print("[!] ERROR: Unsupported platform.")
        sys.exit(1)

    if not os.path.isfile(unity_path):
        print(f"[!] ERROR: Unity executable not found. Please install Unity {unity_version}.")
        sys.exit(1)

    return [unity_path]

def find_executable(name: str) -> str | None:
    search_name = name
    if sys.platform == "win32":
        search_name += ".exe"

    local_path = os.path.abspath(os.path.join(os.getcwd(), search_name))
    if os.path.isfile(local_path) and os.access(local_path, os.X_OK):
        return local_path

    system_path = shutil.which(search_name)
    if system_path:
        return os.path.abspath(system_path)

    return None

def check_prerequisites(command: str) -> None:
    missing_tools = []

    if not find_executable("git"):
        missing_tools.append("git")

    if command == "setup":
        if not find_executable("ffmpeg"):
            missing_tools.append("ffmpeg")

        if not find_executable("AssetRipper.GUI.Free"):
            missing_tools.append("AssetRipper.GUI.Free")

        if not find_executable("vgmstream-cli"):
            missing_tools.append("vgmstream-cli")

        if "CI" not in os.environ:
            find_unity()

    if missing_tools:
        print("[!] ERROR: The following prerequisites are missing:")
        for tool in missing_tools:
            print(f"- {tool}")
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
    assetripper_path = find_executable("AssetRipper.GUI.Free")
    cmd = [
        assetripper_path,
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

def swap_files_dict(swap_dict: dict) -> None:
    for src, dst in swap_dict.items():
        src_path = os.path.join(WORKSPACE_DIR, src)
        dst_path = os.path.join(WORKSPACE_DIR, dst)

        if os.path.isfile(src_path) and os.path.isfile(dst_path):
            print(f"[*] Swapping '{src}' and '{dst}'...")
            swap_files(src_path, dst_path)
        else:
            print(f"[!] WARNING: Cannot swap '{src}' and '{dst}' because one or both files do not exist.")

def swap_files(src: str, dst: str) -> None:
    temp_path = dst + ".temp"
    shutil.move(src, temp_path)
    shutil.move(dst, src)
    shutil.move(temp_path, dst)

def apply_deterministic_guids(new_assets_only: bool) -> None:
    file_list = []

    if new_assets_only:
        print("[*] Identifying new .meta files...")

        git_path = find_executable("git")

        try:
            untracked_cmd = [git_path, "ls-files", "--others", "--exclude-standard"]
            untracked_files = subprocess.check_output(untracked_cmd, cwd=WORKSPACE_DIR, text=True).splitlines()

            file_list = [f for f in untracked_files if f.endswith(".meta")]
        except subprocess.CalledProcessError:
            print("[!] ERROR: Failed to get untracked files from Git.")
            sys.exit(1)

        if not file_list:
            print("[*] No new .meta files found.")
            return
    else:
        print("[*] Scanning for all .meta files...")
        for root, dirs, files in os.walk(WORKSPACE_DIR):
            if ".git" in root:
                continue

            for file in files:
                if file.endswith(".meta"):
                    relative_path = os.path.relpath(os.path.join(root, file), WORKSPACE_DIR)
                    file_list.append(relative_path)

    print(f"[*] Calculating deterministic GUIDs for {len(file_list)} files...")
    guid_map = {}

    for meta_path in file_list:
        full_path = os.path.join(WORKSPACE_DIR, meta_path)
        if not os.path.exists(full_path):
            print(f"[!] WARNING: .meta file '{meta_path}' does not exist. Skipping.")
            continue

        seed_path = meta_path.replace(os.path.sep, '/')
        new_guid = hashlib.md5(seed_path.encode()).hexdigest()

        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            match = re.search(r'guid: ([a-f0-9]{32})', content)
            if not match:
                print(f"[!] WARNING: No GUID found in '{meta_path}'. Skipping.")
                continue

            old_guid = match.group(1)
            if old_guid == new_guid:
                print(f"[*] GUID for '{meta_path}' is already deterministic. Skipping.")
                continue

            guid_map[old_guid] = new_guid
            new_content = content.replace(f"guid: {old_guid}", f"guid: {new_guid}")
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            print(f"[!] ERROR: Failed to process '{meta_path}': {e}")
            sys.exit(1)

    if not guid_map:
        print("[*] No GUIDs need to be updated.")
        return

    print(f"[*] Updating references to {len(guid_map)} assets...")

    guid_pattern = re.compile(r'\b([a-f0-9]{32})\b')

    def guid_replacer(guid_match: re.Match) -> str:
        found_guid = guid_match.group(1)
        return guid_map.get(found_guid, found_guid)

    for root, dirs, files in os.walk(WORKSPACE_DIR):
        if ".git" in root:
            continue

        for file in files:
            # todo: don't process binary files

            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    old_text = f.read()

                new_text = guid_pattern.sub(guid_replacer, old_text)

                if new_text != old_text:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_text)
            except Exception as e:
                print(f"[!] ERROR: Failed to update references in '{file_path}': {e}")
                sys.exit(1)

    print("[+] GUID regeneration finished.")

def get_file_hash(file_path: str) -> str:
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)

    return hasher.hexdigest()

def get_meta_filtered(file_path: str) -> str:
    if not os.path.exists(file_path):
        return ""

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        filtered_liens = [line for line in lines if not line.startswith("guid: ")]
        return "".join(filtered_liens)
    except Exception as e:
        print(f"[!] ERROR: Failed to read and filter '{file_path}': {e}")
        return ""

def deduplicate_assets() -> int:
    print("[*] Scanning for duplicate assets...")

    asset_map = collections.defaultdict(list)
    duplicate_pattern = re.compile(r"^(.*?)(?:_(\d+))?(\.[^.]+)$")
    guid_map = {}

    for root, _, files in os.walk(os.path.join(WORKSPACE_DIR, "Assets")):
        if ".git" in root:
            continue

        for file in files:
            if file.endswith(".meta"):
                continue

            match = duplicate_pattern.match(file)
            if match:
                base_name = match.group(1)
                extension = match.group(3)
                asset_map[(root, base_name, extension)].append(os.path.join(root, file))

    count = 0
    for (_, _, _), paths in asset_map.items():
        if len(paths) < 2:
            continue

        paths.sort(key=lambda x: (len(x), x))
        kept_variants = []

        for asset_path in paths:
            try:
                current_hash = get_file_hash(asset_path)
                current_meta = asset_path + ".meta"
                current_meta_content = get_meta_filtered(current_meta)

                with open(current_meta, "r", encoding="utf-8", errors="ignore") as f:
                    guid_match = re.search(r'guid: ([a-f0-9]{32})', f.read())
                    if not guid_match:
                        continue
                    current_guid = guid_match.group(1)

                matching_guid = None
                for m_hash, m_meta, m_guid in kept_variants:
                    if current_hash == m_hash and current_meta_content == m_meta:
                        matching_guid = m_guid
                        break

                if matching_guid:
                    print(f"[*] Removing duplicate asset '{asset_path}'...")
                    os.remove(asset_path)
                    if os.path.isfile(current_meta):
                        guid_map[current_guid] = matching_guid
                        os.remove(current_meta)
                    count += 1
                else:
                    kept_variants.append((current_hash, current_meta_content, current_guid))

            except Exception as e:
                print(f"[!] ERROR: Failed to process '{asset_path}': {e}")
                continue

    if count > 0:
        print(f"[+] Removed {count} duplicate assets.")
    else:
        print("[*] No duplicate assets found.")
        return 0

    if not guid_map:
        print("[*] No GUIDs need to be updated after deduplication.")
        return 0

    print(f"[*] Updating references to {len(guid_map)} deduplicated assets...")

    guid_pattern = re.compile(r'\b([a-f0-9]{32})\b')

    def guid_replacer(guid_match: re.Match) -> str:
        found_guid = guid_match.group(1)
        return guid_map.get(found_guid, found_guid)

    for root, dirs, files in os.walk(WORKSPACE_DIR):
        if ".git" in root:
            continue

        for file in files:
            # todo: don't process binary files

            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    old_text = f.read()

                new_text = guid_pattern.sub(guid_replacer, old_text)

                if new_text != old_text:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_text)
            except Exception as e:
                print(f"[!] ERROR: Failed to update references in '{file_path}': {e}")
                sys.exit(1)

    print("[+] Deduplication reference update finished.")
    return count

class FlowDict(dict):
    pass

def represent_flow_dict(self: yaml.Dumper, data: FlowDict) -> yaml.Node:
    return self.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True)

def represent_none(self: yaml.Dumper, _) -> yaml.Node:
    return self.represent_scalar("tag:yaml.org,2002:str", " ")

def populate_texture_platform_settings() -> None:
    print("[*] Populating texture platform settings...")

    yaml.add_representer(FlowDict, represent_flow_dict)
    yaml.add_representer(type(None), represent_none)

    REQUIRED_ORDER = ["DefaultTexturePlatform", "Standalone", "Android", "iPhone", "WebGL"]

    png_metas = glob.glob(os.path.join(WORKSPACE_DIR, "Assets", "**", "*.png.meta"), recursive=True)
    for meta_path in png_metas:
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "TextureImporter" not in data:
                print(f"[!] WARNING: No TextureImporter section found in '{meta_path}'. Skipping.")
                continue

            importer = data["TextureImporter"]
            if "platformSettings" not in importer:
                continue

            settings_list = importer["platformSettings"]

            existing_targets = collections.defaultdict(list)
            for entry in settings_list:
                name = entry.get("buildTarget")
                existing_targets[name].append(entry)

            standalone_template = None
            if existing_targets["Standalone"]:
                standalone_template = existing_targets["Standalone"][0]
            elif existing_targets["DefaultTexturePlatform"]:
                standalone_template = existing_targets["DefaultTexturePlatform"][0]

            if not standalone_template:
                print(f"[!] WARNING: No suitable template found for '{meta_path}'. Skipping.")
                continue

            new_settings_list = []
            modified = False

            for target in REQUIRED_ORDER:
                if target in existing_targets:
                    new_settings_list.extend(existing_targets[target])
                else:
                    new_entry = standalone_template.copy()
                    new_entry["buildTarget"] = target
                    new_entry["overridden"] = 0
                    new_settings_list.append(new_entry)
                    modified = True

            for target_name, entries in existing_targets.items():
                if target_name not in REQUIRED_ORDER:
                    new_settings_list.extend(entries)

            if not modified and new_settings_list != settings_list:
                modified = True

            if modified:
                importer["platformSettings"] = new_settings_list

                for key in ["spritePivot", "spriteBorder"]:
                    if key in importer and isinstance(importer[key], dict):
                        importer[key] = FlowDict(importer[key])

                if "spriteSheet" in importer:
                    sheet = importer["spriteSheet"]
                    if "outline" in sheet and isinstance(sheet["outline"], list):
                        for polygon in sheet["outline"]:
                            if isinstance(polygon, list):
                                for i in range(len(polygon)):
                                    if isinstance(polygon[i], dict):
                                        polygon[i] = FlowDict(polygon[i])

                with open(meta_path, "w", encoding="utf-8") as f:
                    content = yaml.dump(data, sort_keys=False)
                    content = content.replace("' '", "")
                    f.write(content)

                print(f"[*] Updated platform settings in '{meta_path}'.")
        except Exception as e:
            print(f"[!] ERROR: Failed to process '{meta_path}': {e}")
            sys.exit(1)

def cmd_setup(apk_path: str, bundles_path: str) -> None:
    check_prerequisites("setup")
    git_path = find_executable("git")

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

    # https://github.com/SamboyCoding/Fmod5Sharp/issues/9
    print("[*] Re-encoding .wav files...")
    ffmpeg_path = find_executable("ffmpeg")
    wav_files = glob.glob(os.path.join(WORKSPACE_DIR, "Assets", "**", "*.wav"), recursive=True)
    for wav_file in wav_files:
        temp_wav_file = wav_file + ".temp.wav"
        run_cmd([
            ffmpeg_path,
            "-y",
            "-i",
            wav_file,
            "-map_metadata",
            "0",
            temp_wav_file
        ])

        shutil.move(temp_wav_file, wav_file)

    # https://github.com/SamboyCoding/Fmod5Sharp/issues/12
    print("[*] Decoding MPEG FSB files...")
    vgmstream_path = find_executable("vgmstream-cli")
    fsb_files = glob.glob(os.path.join(WORKSPACE_DIR, "Assets", "sound", "**", "*.audioclip.resS"), recursive=True)
    for fsb_file in fsb_files:
        # We need to add the .fsb extension for vgmstream to recognize the file format
        temp_fsb_file = fsb_file + ".fsb"
        shutil.move(fsb_file, temp_fsb_file)

        output_wav_file = fsb_file.replace(".audioclip.resS", ".wav")
        run_cmd([
            vgmstream_path,
            temp_fsb_file,
            "-o",
            output_wav_file
        ])

        os.remove(temp_fsb_file)

        audio_name = os.path.splitext(os.path.basename(output_wav_file))[0]
        audioclip_path = os.path.join(os.path.dirname(output_wav_file), audio_name + ".audioclip")
        os.remove(audioclip_path)

        old_audio_meta_path = audioclip_path + ".meta"
        new_audio_meta_path = output_wav_file + ".meta"
        shutil.move(old_audio_meta_path, new_audio_meta_path)

        with open(new_audio_meta_path, "r", encoding="utf-8") as f:
            meta_content = f.read()

        audio_guid = re.search(r'guid: ([a-f0-9]{32})', meta_content).group(1)
        audio_asset_bundle_name = re.search(r'assetBundleName: (.+)', meta_content).group(1)

        meta_content = (
            f"fileFormatVersion: 2\n"
            f"guid: {audio_guid}\n"
            f"AudioImporter:\n"
            f"  externalObjects: {{}}\n"
            f"  serializedVersion: 7\n"
            f"  defaultSettings:\n"
            f"    serializedVersion: 2\n"
            f"    loadType: 2\n"
            f"    sampleRateSetting: 0\n"
            f"    sampleRateOverride: 0\n"
            f"    compressionFormat: 1\n"
            f"    quality: 0\n"
            f"    conversionMode: 0\n"
            f"    preloadAudioData: 1\n"
            f"  platformSettingOverrides: {{}}\n"
            f"  forceToMono: 0\n"
            f"  normalize: 0\n"
            f"  loadInBackground: 1\n"
            f"  ambisonic: 0\n"
            f"  3D: 0\n"
            f"  userData: \n"
            f"  assetBundleName: {audio_asset_bundle_name}\n"
            f"  assetBundleVariant: \n"
        )

        with open(new_audio_meta_path, "w", encoding="utf-8") as f:
            f.write(meta_content)

    if sys.platform == "linux":
        print("[*] Fixing Stryder EType duplicate asset...")
        stryder_src = os.path.join(WORKSPACE_DIR, "Assets", "Material", "MAT_SB_StryderEtype.mat")
        stryder_meta_src = stryder_src + ".meta"
        stryder_dst = os.path.join(WORKSPACE_DIR, "Assets", "Material", "MAT_SB_StryderEtype_0.mat")
        stryder_meta_dst = stryder_dst + ".meta"

        if os.path.isfile(stryder_src) and os.path.isfile(stryder_meta_src):
            shutil.move(stryder_src, stryder_dst)
            shutil.move(stryder_meta_src, stryder_meta_dst)
        else:
            print(f"[!] WARNING: Couldn't find duplicate Stryder EType material. Skipping.")

    print("[*] Fixing MainUI/StoreUI...")
    swap_dict = {
        "Assets/Scenes/MainUI.unity": "Assets/Scenes/StoreUI.unity",
        "Assets/Scenes/MainUI.unity.meta": "Assets/Scenes/StoreUI.unity.meta",
        "Assets/Scenes/MainUI/LightProbes.asset": "Assets/Scenes/StoreUI/LightProbes.asset",
        "Assets/Scenes/MainUI/LightProbes.asset.meta": "Assets/Scenes/StoreUI/LightProbes.asset.meta",
        "Assets/Scenes/MainUI/LightingData.asset": "Assets/Scenes/StoreUI/LightingData.asset",
        "Assets/Scenes/MainUI/LightingData.asset.meta": "Assets/Scenes/StoreUI/LightingData.asset.meta"
    }

    swap_files_dict(swap_dict)

    print("[*] Regenerating deterministic asset GUIDs...")
    apply_deterministic_guids(False)

    while True:
        removed = deduplicate_assets()
        if removed == 0:
            break

    print("[*] Copy overrides...")
    overrides_dst = os.path.join(WORKSPACE_DIR, "Assets")
    shutil.copytree(OVERRIDES_DIR, overrides_dst, dirs_exist_ok=True)

    print("[*] Extract app icon...")
    icon_src = os.path.join(apk_extract_path, "res", "drawable-xxxhdpi-v4", "app_icon.png")
    if os.path.isfile(icon_src):
        icon_dst = os.path.join(WORKSPACE_DIR, "Assets", "Texture2D", "app_icon.png")
        shutil.copyfile(icon_src, icon_dst)
    else:
        print(f"[!] WARNING: App icon not found at expected location '{icon_src}'!")

    print("[*] Deleting broken game board mesh...")
    broken_mesh_path = os.path.join(WORKSPACE_DIR, "Assets", "Mesh", "Combined Mesh (root_ scene).asset")
    os.remove(broken_mesh_path)
    os.remove(broken_mesh_path + ".meta")

    print("[*] Deleting old lightmap data...")
    cubemap_dir = os.path.join(WORKSPACE_DIR, "Assets", "Cubemap")
    shutil.rmtree(cubemap_dir, ignore_errors=True)
    gameboard_lightmap = os.path.join(WORKSPACE_DIR, "Assets", "Scenes", "GameBoard1", "Lightmap-0_comp_light.texture2D")
    os.remove(gameboard_lightmap)
    os.remove(gameboard_lightmap + ".meta")

    print("[*] Copy gitignore...")
    gitignore_src = os.path.join(os.path.dirname(__file__), "unity.gitignore")
    gitignore_dst = os.path.join(WORKSPACE_DIR, ".gitignore")
    shutil.copyfile(gitignore_src, gitignore_dst)

    print("[*] Initializing Git repository...")
    run_cmd([git_path, "init"], cwd=WORKSPACE_DIR)
    run_cmd([git_path, "config", "core.autocrlf", "false"], cwd=WORKSPACE_DIR)
    run_cmd([git_path, "add", "."], cwd=WORKSPACE_DIR)
    run_cmd([git_path, "commit", "-m", "AssetRipper", "--author", "TF Reclaimed <auto@mated.null>"], cwd=WORKSPACE_DIR)
    run_cmd([git_path, "tag", "raw-project"], cwd=WORKSPACE_DIR)

    pre_patches = sorted(glob.glob(os.path.abspath(os.path.join(PRE_PATCHES_DIR, "*.patch"))))
    if pre_patches:
        print(f"[*] Applying {len(pre_patches)} pre-patches...")
        run_cmd([git_path, "am", "--3way", "--ignore-whitespace"] + pre_patches, cwd=WORKSPACE_DIR)

    print("[*] Upgrading and reserializing Unity project...")
    print("[*] This may take several minutes. Please wait...")

    unity_cmd = find_unity()
    unity_log = os.path.abspath(os.path.join(TEMP_DIR, "unity_upgrade.log"))
    unity_args = [
        "-quit",
        "-batchmode",
        "-nographics",
        "-projectPath",
        os.path.abspath(WORKSPACE_DIR),
        "-executeMethod",
        "AssetUpgrader.UpgradeProject"
    ]

    if "CI" in os.environ:
        unity_log = "/dev/stdout"
        unity_args += [
            "-serial",
            os.environ.get("UNITY_SERIAL"),
            "-username",
            os.environ.get("UNITY_EMAIL"),
            "-password",
            os.environ.get("UNITY_PASSWORD"),
        ]

    unity_args += ["-logFile", unity_log]
    run_cmd(unity_cmd + unity_args)

    print("[+] Finished project upgrade!")

    if "CI" in os.environ:
        print("[*] Fixing file permissions...")
        run_cmd([
            "sudo",
            "chown",
            "-R",
            f"{os.getuid()}:{os.getgid()}",
            WORKSPACE_DIR
        ])

    print("[*] Regenerating deterministic asset GUIDs... (new assets)")
    apply_deterministic_guids(True)

    populate_texture_platform_settings()

    print("[*] Committing upgraded project...")
    run_cmd([git_path, "add", "."], cwd=WORKSPACE_DIR)
    run_cmd([git_path, "commit", "-m", "Base project", "--author", "TF Reclaimed <auto@mated.null>"], cwd=WORKSPACE_DIR)
    run_cmd([git_path, "tag", "base-project"], cwd=WORKSPACE_DIR)

    patches = sorted(glob.glob(os.path.abspath(os.path.join(PATCHES_DIR, "*.patch"))))
    if patches:
        print(f"[*] Applying {len(patches)} patches...")
        run_cmd([git_path, "am", "--3way", "--ignore-whitespace"] + patches, cwd=WORKSPACE_DIR)
    else:
        print("[*] No patches found to apply.")

    print("[*] Deleting temporary files...")
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    shutil.rmtree("temp", ignore_errors=True) # AssetRipper

    print(f"[+] Setup completed successfully! You can now open '{WORKSPACE_DIR}' in Unity.")

def cmd_rebuild() -> None:
    check_prerequisites("rebuild")
    git_path = find_executable("git")

    if not os.path.exists(WORKSPACE_DIR):
        print(f"[!] ERROR: Workspace directory '{WORKSPACE_DIR}' does not exist. Please run 'setup' first.")
        sys.exit(1)

    os.makedirs(PRE_PATCHES_DIR, exist_ok=True)
    os.makedirs(PATCHES_DIR, exist_ok=True)

    print("[*] Rebuilding patches...")
    for patch in glob.glob(os.path.join(PRE_PATCHES_DIR, "*.patch")):
        os.remove(patch)

    export_flags = [
        "--zero-commit",
        "--no-numbered",
        "--no-stat",
        "--no-signature",
        "--unified=1",
        "--minimal",
        "--ignore-cr-at-eol"
    ]

    result = subprocess.run([git_path, "rev-parse", "--verify", "base-project"], cwd=WORKSPACE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    has_base = (result.returncode == 0)

    if not has_base:
        print("[!] 'base-project' tag not found.")
        print(f"[*] Exporting pre-patches...")
        run_cmd([
            git_path,
            "format-patch",
            "raw-project..HEAD",
            "-o",
            os.path.abspath(PRE_PATCHES_DIR)
        ] + export_flags, cwd=WORKSPACE_DIR)

        print("[+] Pre-patches rebuilt successfully.")
        return

    print("[*] Exporting pre-patches...")
    run_cmd([
        git_path,
        "format-patch",
        "raw-project..base-project^",
        "-o",
        os.path.abspath(PRE_PATCHES_DIR)
    ] + export_flags, cwd=WORKSPACE_DIR)

    print("[*] Exporting patches...")
    for patch in glob.glob(os.path.join(PATCHES_DIR, "*.patch")):
        os.remove(patch)

    run_cmd([
        git_path,
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