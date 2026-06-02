#!/usr/bin/env python3
"""
Minimal VSIX builder for the energy-estimator extension.
A .vsix is a ZIP with a specific manifest structure.
Run from the extension root directory.
"""
import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent

def read_package_json():
    with open(ROOT / "package.json") as f:
        return json.load(f)

def content_types_xml():
    return """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension=".json" ContentType="application/json"/>
  <Default Extension=".js" ContentType="application/javascript"/>
  <Default Extension=".py" ContentType="text/plain"/>
  <Default Extension=".md" ContentType="text/plain"/>
  <Default Extension=".txt" ContentType="text/plain"/>
  <Default Extension=".ts" ContentType="text/plain"/>
  <Default Extension=".vsixmanifest" ContentType="text/xml"/>
  <Default Extension=".png" ContentType="image/png"/>
  <Default Extension=".sh" ContentType="text/plain"/>
  <Default Extension=".joblib" ContentType="application/octet-stream"/>
  <Default Extension=".csv" ContentType="text/plain"/>
</Types>"""

def vsix_manifest(pkg):
    name = pkg["name"]
    publisher = pkg.get("publisher", "unknown")
    version = pkg["version"]
    display_name = pkg.get("displayName", name)
    description = pkg.get("description", "")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0"
    xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011"
    xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="{name}" Version="{version}" Publisher="{publisher}"/>
    <DisplayName>{display_name}</DisplayName>
    <Description xml:space="preserve">{description}</Description>
    <Tags>python,energy,performance,green coding</Tags>
    <GalleryFlags>Public</GalleryFlags>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.75.0"/>
    </Properties>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>
  </Assets>
</PackageManifest>"""

# Files to include (relative to ROOT), mapped to their path inside the ZIP
INCLUDE_PATTERNS = [
    ("package.json",   "extension/package.json"),
    ("README.md",      "extension/README.md"),
    ("QUICKSTART.md",  "extension/QUICKSTART.md"),
    (".env",           "extension/.env"),   # API key fallback for Python scripts
]

OUT_DIRS = [
    ("out",    "extension/out"),
]

PYTHON_DIR = ("python", "extension/python")

EXCLUDE_NAMES = {"__pycache__", "node_modules"}
EXCLUDE_EXTENSIONS = {".pyc"}

def collect_files():
    entries = []

    # Single files
    for src_rel, dst in INCLUDE_PATTERNS:
        src = ROOT / src_rel
        if src.exists():
            entries.append((src, dst))

    # out/ directory
    for src_dir_rel, dst_prefix in OUT_DIRS:
        src_dir = ROOT / src_dir_rel
        if src_dir.exists():
            for f in src_dir.rglob("*"):
                if f.is_file() and f.suffix not in EXCLUDE_EXTENSIONS:
                    rel = f.relative_to(ROOT / src_dir_rel)
                    entries.append((f, f"{dst_prefix}/{rel}"))

    # python/ directory (exclude __pycache__, .pyc)
    python_src, python_dst = PYTHON_DIR
    python_dir = ROOT / python_src
    if python_dir.exists():
        for f in python_dir.rglob("*"):
            if f.is_file():
                if f.suffix in EXCLUDE_EXTENSIONS:
                    continue
                if any(part in EXCLUDE_NAMES for part in f.parts):
                    continue
                rel = f.relative_to(ROOT / python_src)
                entries.append((f, f"{python_dst}/{rel}"))

    return entries


def main():
    pkg = read_package_json()
    name = pkg["name"]
    version = pkg["version"]
    out_path = ROOT / f"{name}-{version}.vsix"

    print(f"Building {out_path.name} ...")
    files = collect_files()

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml())
        zf.writestr("extension.vsixmanifest", vsix_manifest(pkg))
        for src, dst in files:
            print(f"  + {dst}")
            zf.write(src, dst)

    size_kb = out_path.stat().st_size // 1024
    print(f"\nDone: {out_path}  ({size_kb} KB)")
    print(f"\nInstall with:")
    print(f"  code --install-extension {out_path.name}")


if __name__ == "__main__":
    main()
