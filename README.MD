# FrontlinePatcher

A patch based Titanfall Frontline modding tool.

## Setting up the workspace

1. Download Titanfall Frontline APK and bundles from our [CDN](https://cdn.tfflinternal.com/original/). Extract the bundle archive.
2. Clone this repository.
3. Install the following dependencies:
   - Python 3
   - Git
   - FFmpeg
   - AssetRipper (Free, 1.3.12)
   - vgmstream-cli (r2083)
   - Unity (2022.3.62f3)
   - You can place their executables in the same directory as `patcher.py`, or in the PATH, the system will find them automatically. Unity must be installed in its default location.
4. Install Python dependencies with `pip install -r requirements.txt`.
5. Run `patcher.py setup <path-to-apk> <path-to-bundles>`.
6. You can now open `RippedProject` in Unity.

## Creating a patch

1. Make some change to `RippedProject`.
2. Run `git add` and `git commit` as you normally would in the `RippedProject` directory.
3. Run `patcher.py rebuild` to create a patch from your changes.

Reordering, modifying, and deleting patches can be done with `git rebase -i base-project` and then running `patcher.py rebuild` again.