"""Deploys a release to GitHub with packaged dist ZIP archive and release notes."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_ROOT = ROOT / "dist"
VERSION_FILE = ROOT / "VERSION"
RELEASE_NOTES_FILE = ROOT / "release_notes.md"
ENV_FILE = ROOT / ".env"
DEFAULT_REPO = "Vetrox2/ad_skipper"


def load_env() -> None:
    """Loads environment variables from .env if present."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_version(v: str) -> tuple[int, int, int]:
    cleaned = v.lstrip("vV").strip()
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", cleaned)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3)) if match.group(3) is not None else 0
        return (major, minor, patch)
    return (0, 0, 0)


def get_latest_version() -> str:
    versions: list[str] = []

    if VERSION_FILE.exists():
        v = VERSION_FILE.read_text(encoding="utf-8").strip()
        if v:
            versions.append(v)

    if DIST_ROOT.exists():
        for item in DIST_ROOT.iterdir():
            if item.is_dir():
                m = re.search(r"(\d+\.\d+(?:\.\d+)?)", item.name)
                if m:
                    versions.append(m.group(1))

    if not versions:
        raise ValueError("No version found in VERSION file or dist/ directory.")

    return max(versions, key=parse_version)


def get_dist_dir(version: str) -> Path:
    cleaned = version.lstrip("vV").strip()
    return DIST_ROOT / f"ad_skipper_v{cleaned}"


def create_dist_zip(dist_dir: Path, zip_path: Path) -> Path:
    """Compresses the distribution directory into a zip archive."""
    print(f"Creating ZIP archive from: {dist_dir} -> {zip_path.name}")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    folder_name = dist_dir.name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(dist_dir):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(dist_dir)
                zipf.write(file_path, arcname=f"{folder_name}/{rel_path}")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  Archive created ({size_mb:.2f} MB)")
    return zip_path


def get_release_notes(version: str) -> str:
    """Reads release notes from release_notes.md or returns a default template."""
    if RELEASE_NOTES_FILE.exists():
        content = RELEASE_NOTES_FILE.read_text(encoding="utf-8").strip()
        if content:
            return content

    return (
        f"## Release v{version}\n\n"
        f"Automated release package for Ad Skipper v{version}.\n\n"
        f"### What's Changed\n"
        f"- Release build `ad_skipper_v{version}`\n"
    )


def get_github_repo() -> str:
    """Gets repository (owner/repo) from git remote or defaults."""
    env_repo = os.getenv("GITHUB_REPOSITORY")
    if env_repo:
        return env_repo

    try:
        res = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            url = res.stdout.strip()
            # Match https://github.com/owner/repo.git or git@github.com:owner/repo.git
            m = re.search(r"github\.com[:/]([^/]+)/([^/\.]+)(?:\.git)?", url)
            if m:
                return f"{m.group(1)}/{m.group(2)}"
    except Exception:
        pass

    return DEFAULT_REPO


def _get_token_from_gh_cli() -> str | None:
    """Tries to get token from GitHub CLI (gh auth token)."""
    try:
        res = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return None


def _get_token_from_git_credential() -> str | None:
    """Tries to retrieve GitHub token from Git Credential Manager (Windows Credential Manager)."""
    try:
        res = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            data = dict(line.split("=", 1) for line in res.stdout.splitlines() if "=" in line)
            pwd = data.get("password", "").strip()
            if pwd:
                return pwd
    except Exception:
        pass
    return None


def get_github_token() -> str:
    """Retrieves GitHub token securely with fallbacks:

    1. GITHUB_TOKEN or GH_TOKEN from environment.
    2. GitHub CLI (gh auth token).
    3. Git Credential Manager (logged in Git session from Windows Credential Manager).
    4. .env file (optional local fallback).
    """
    # 1. Environment variable
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token and token.strip():
        return token.strip()

    # 2. GitHub CLI
    cli_token = _get_token_from_gh_cli()
    if cli_token:
        return cli_token

    # 3. Git Credential Manager
    gcm_token = _get_token_from_git_credential()
    if gcm_token:
        return gcm_token

    # 4. .env fallback
    load_env()
    env_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    raise ValueError(
        "GitHub token could not be resolved automatically.\n"
        "Ways to authenticate:\n"
        "  1. Log in via Git / Git Credential Manager ('git push' already uses this)\n"
        "  2. Log in via GitHub CLI: 'gh auth login'\n"
        "  3. Set GITHUB_TOKEN in your environment or .env file"
    )



def github_api_request(
    url: str,
    token: str,
    method: str = "GET",
    data: bytes | None = None,
    content_type: str = "application/vnd.github+json",
) -> dict | list | None:
    """Performs an authenticated request to the GitHub API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ad-skipper-release-tool",
    }
    if content_type:
        headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            if resp.status == 204 or not body:
                return None
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub API error {exc.code} for {method} {url}: {err_body}") from exc


def deploy_release(version: str, zip_path: Path, release_notes: str) -> None:
    load_env()
    token = get_github_token()
    repo = get_github_repo()
    tag_name = f"v{version.lstrip('vV')}"
    release_title = f"Ad Skipper {tag_name}"

    print(f"=== Deploying {tag_name} to GitHub ({repo}) ===")

    # 1. Check if release already exists for this tag
    get_release_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag_name}"
    existing_release: dict | None = None
    try:
        res = github_api_request(get_release_url, token)
        if isinstance(res, dict):
            existing_release = res
    except RuntimeError:
        existing_release = None

    if existing_release:
        release_id = existing_release["id"]
        print(f"Found existing release ID {release_id}. Updating release notes...")
        patch_url = f"https://api.github.com/repos/{repo}/releases/{release_id}"
        patch_payload = json.dumps({
            "name": release_title,
            "body": release_notes,
        }).encode("utf-8")
        release = github_api_request(patch_url, token, method="PATCH", data=patch_payload)

        # Remove existing asset with the same name if present
        for asset in existing_release.get("assets", []):
            if asset.get("name") == zip_path.name:
                asset_id = asset["id"]
                print(f"Deleting old asset ID {asset_id} ({zip_path.name})...")
                del_url = f"https://api.github.com/repos/{repo}/releases/assets/{asset_id}"
                github_api_request(del_url, token, method="DELETE")
    else:
        print(f"Creating new GitHub release for tag '{tag_name}'...")
        create_url = f"https://api.github.com/repos/{repo}/releases"
        create_payload = json.dumps({
            "tag_name": tag_name,
            "name": release_title,
            "body": release_notes,
            "draft": False,
            "prerelease": False,
        }).encode("utf-8")
        release = github_api_request(create_url, token, method="POST", data=create_payload)

    # 2. Upload asset
    release_id = release["id"]
    upload_url_template = release.get("upload_url", "")
    upload_base_url = upload_url_template.split("{")[0]
    upload_url = f"{upload_base_url}?name={urllib.parse.quote(zip_path.name)}"

    print(f"Uploading asset {zip_path.name} to release ID {release_id}...")
    zip_bytes = zip_path.read_bytes()
    github_api_request(
        upload_url,
        token,
        method="POST",
        data=zip_bytes,
        content_type="application/zip",
    )

    html_url = release.get("html_url", f"https://github.com/{repo}/releases/tag/{tag_name}")
    print(f"\n[SUCCESS] Release successfully published: {html_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Package and deploy ad_skipper release to GitHub.")
    parser.add_argument(
        "version_pos",
        nargs="?",
        default=None,
        help="Target version to release (e.g. 0.2.2). If omitted, releases the latest build.",
    )
    parser.add_argument(
        "-v",
        "--version",
        dest="version_flag",
        default=None,
        help="Target version to release (e.g. 0.2.2). If omitted, releases the latest build.",
    )
    args = parser.parse_args()

    version_input = args.version_flag or args.version_pos
    if version_input:
        target_version = version_input.lstrip("vV").strip()
    else:
        target_version = get_latest_version()

    dist_dir = get_dist_dir(target_version)
    if not dist_dir.exists():
        print(f"Error: Distribution directory not found: {dist_dir}")
        print(f"Please run 'pipenv run build' or 'python build.py {target_version}' first.")
        sys.exit(1)

    zip_filename = f"ad_skipper_v{target_version}.zip"
    zip_path = DIST_ROOT / zip_filename
    create_dist_zip(dist_dir, zip_path)

    release_notes = get_release_notes(target_version)
    print(f"\n--- Release Notes ({'from release_notes.md' if RELEASE_NOTES_FILE.exists() else 'default'}) ---")
    print(release_notes)
    print("--------------------------------------------------\n")

    try:
        deploy_release(target_version, zip_path, release_notes)
    except Exception as exc:
        print(f"\n[FAILED] Error deploying release: {exc}")
        print(f"Local package is ready at: {zip_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
