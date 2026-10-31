#!/usr/bin/env python3
"""Build and run the real iOS display layer with synthetic services in a simulator.

This is a layout probe, not a playable game. No keys or game assets are needed.
Open/close the Duo in Xcode Device Hub; Documents/checks.json updates each second.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
GAME = "0100A3501946E000"
BUNDLE = "org.ot2.displaycheck"


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--udid", required=True, help="Existing iOS simulator UDID")
    parser.add_argument("--work", type=Path, required=True, help="Scratch build directory")
    args = parser.parse_args()
    devices = json.loads(run("xcrun", "simctl", "list", "devices", "available", "-j",
                             capture_output=True, text=True).stdout)["devices"]
    device = next((d for runtime, rows in devices.items() if ".iOS-" in runtime
                   for d in rows if d["udid"] == args.udid), None)
    if not device:
        parser.error("--udid must identify an available iOS simulator, not a physical device")
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    resources = work / "dm"
    resources.mkdir(exist_ok=True)
    (resources / "display.json").write_text(json.dumps({
        "game": GAME, "mount": "../../../", "path": "Test/Config.ini",
        "overlay_path": "Test/test.pak",
        "profile": "r.setres=${DISPLAY_RESOLUTION}\nr.setres=${DISPLAY_RESOLUTION}\n",
    }))
    run(sys.executable, REPO / "dm/games/game.py", "header", GAME, work / "game_profile.h")
    properties = {
        "UILaunchScreen": {}, "UIRequiresFullScreen": True,
        "UIStatusBarHidden": True, "UIViewControllerBasedStatusBarAppearance": False,
        "UISupportedInterfaceOrientations": ["UIInterfaceOrientationLandscapeRight",
                                              "UIInterfaceOrientationLandscapeLeft"],
        "UIApplicationSceneManifest": {"UIApplicationSupportsMultipleScenes": False,
            "UISceneConfigurations": {"UIWindowSceneSessionRoleApplication": [{
                "UISceneConfigurationName": "Default", "UISceneDelegateClassName": "SceneDelegate"}]}},
    }
    spec = {"name": "DisplayCheck", "options": {"deploymentTarget": {"iOS": "18.0"}},
        "targets": {"DisplayCheck": {"type": "application", "platform": "iOS",
            "sources": [{"path": str(REPO / "dm/ios/tests/display_app/Main.m")},
                        {"path": str(REPO / "dm/ios/Sources/DisplayConfig.m")},
                        {"path": str(resources), "type": "folder"}],
            "settings": {"PRODUCT_BUNDLE_IDENTIFIER": BUNDLE, "TARGETED_DEVICE_FAMILY": "1,2",
                "CLANG_ENABLE_OBJC_ARC": True, "CODE_SIGNING_ALLOWED": False,
                "HEADER_SEARCH_PATHS": [str(REPO / "dm/host"), str(work)]},
            "info": {"path": "Info.plist", "properties": properties}}}}
    spec_path = work / "project.json"
    spec_path.write_text(json.dumps(spec, indent=2))
    run("xcodegen", "generate", "--spec", spec_path, "--project", work)
    log = work / "build.log"
    with log.open("w") as stream:
        try:
            run("xcodebuild", "-project", work / "DisplayCheck.xcodeproj", "-scheme", "DisplayCheck",
                "-configuration", "Debug", "-sdk", "iphonesimulator", "-derivedDataPath", work / "dd",
                "CODE_SIGNING_ALLOWED=NO", "build", stdout=stream, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            print(f"Build failed; see {log}", file=sys.stderr)
            raise
    if device["state"] != "Booted":
        run("xcrun", "simctl", "boot", args.udid)
    run("xcrun", "simctl", "install", args.udid, work / "dd/Build/Products/Debug-iphonesimulator/DisplayCheck.app")
    run("xcrun", "simctl", "launch", "--terminate-running-process", args.udid, BUNDLE)
    container = run("xcrun", "simctl", "get_app_container", args.udid, BUNDLE, "data",
                    capture_output=True, text=True).stdout.strip()
    print(f"Layout probe running on {device['name']} (no game code).")
    print(f"Geometry report: {container}/Documents/checks.json")


if __name__ == "__main__":
    main()
