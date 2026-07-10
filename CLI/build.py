#!/usr/bin/env python3
"""
AgentCanvas Build Script (PyInstaller)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Compiles Python source into standalone Windows executables for
distribution with the Unity build.

Output:
    Assets/StreamingAssets/AgentCanvas/
    ├── cli.exe          # Debug CLI (from main.py)
    ├── mcp.exe          # Production MCP Server (from mcp_server.py)
    ├── .env.example     # Configuration template
    ├── index/           # Embedding index cache (runtime)
    └── logs/            # Log files (runtime)

Usage:
    # From project root (where this file lives):
    python build.py

    # Or with options:
    python build.py --output-dir ../Assets/StreamingAssets/AgentCanvas --clean
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


# ── Constants ───────────────────────────────────────────────────────────────

HERE = Path(__file__).parent.resolve()

# Default output: project-root/Assets/StreamingAssets/AgentCanvas/
DEFAULT_OUTPUT = HERE.parent / "Assets" / "StreamingAssets" / "AgentCanvas"

BUILD_ENTRIES = [
    {
        "name": "cli",
        "script": "main.py",
        "description": "Debug CLI tool",
    },
    {
        "name": "mcp",
        "script": "mcp_server.py",
        "description": "Production MCP Server",
    },
]

PYINSTALLER_OPTS = [
    "--onefile",                # Single .exe output
    "--noconsole",              # No console window for production (mcp.exe)
    "--clean",                  # Clean PyInstaller cache
    "--noconfirm",              # Overwrite output without asking
]


# ── Build Logic ─────────────────────────────────────────────────────────────


def find_pyinstaller() -> Optional[str]:
    """Locate PyInstaller in the current Python environment."""
    # Check if pyinstaller is importable
    try:
        import PyInstaller  # noqa: F401
        # PyInstaller is installed, so pyinstaller.exe should be on PATH
        result = subprocess.run(
            ["where", "pyinstaller"],
            capture_output=True, text=True, shell=False,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except ImportError:
        pass

    # Fallback: try running via python -m PyInstaller
    return "pyinstaller"


def build_exe(
    script_name: str,
    exe_name: str,
    work_dir: Path,
    output_dir: Path,
    extra_opts: Optional[List[str]] = None,
    console: bool = True,
) -> bool:
    """
    Build a single .exe from a Python script using PyInstaller.

    Args:
        script_name: Relative path to the Python script (from CLI/)
        exe_name: Desired output executable name (without .exe)
        work_dir: Working directory (CLI/ source root)
        output_dir: Output directory for the .exe
        extra_opts: Additional PyInstaller options
        console: Whether to show a console window (cli.exe=True, mcp.exe=False)

    Returns:
        True if build succeeded, False otherwise.
    """
    pyinstaller = find_pyinstaller()
    if pyinstaller is None:
        print("✗ PyInstaller not found. Install with: pip install pyinstaller>=6.0")
        return False

    script_path = work_dir / script_name
    if not script_path.exists():
        print(f"✗ Script not found: {script_path}")
        return False

    # Build options
    opts = [pyinstaller]

    if not console:
        opts.append("--noconsole")

    opts.extend([
        "--onefile",
        "--clean",
        "--noconfirm",
        "--name", exe_name,
        "--distpath", str(output_dir),
        "--workpath", str(work_dir / "__pycache__" / "pyinstaller"),
        "--specpath", str(work_dir / "__pycache__" / "pyinstaller"),
        "--add-data", f"{work_dir / '.env.example'}{os.pathsep}.env.example",
    ])

    if extra_opts:
        opts.extend(extra_opts)

    opts.append(str(script_path))

    # Run PyInstaller
    print(f"\n{'='*60}")
    print(f"Building {exe_name}.exe from {script_name}...")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            opts,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per build
        )

        if result.returncode != 0:
            print(f"✗ Build failed for {exe_name}.exe")
            print(result.stderr[-2000:] if result.stderr else "")
            return False

        # Verify output exists
        exe_path = output_dir / f"{exe_name}.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"✓ {exe_name}.exe built successfully ({size_mb:.1f} MB)")
            return True
        else:
            print(f"✗ Output not found: {exe_path}")
            return False

    except subprocess.TimeoutExpired:
        print(f"✗ Build timed out for {exe_name}.exe (300s)")
        return False
    except FileNotFoundError:
        print(f"✗ PyInstaller not found at '{pyinstaller}'")
        print("  Install: pip install pyinstaller>=6.0")
        return False
    except Exception as e:
        print(f"✗ Build error for {exe_name}.exe: {e}")
        return False


def copy_assets(output_dir: Path, work_dir: Path) -> None:
    """Copy supporting files to the output directory."""
    # .env.example
    env_example_src = work_dir / ".env.example"
    env_example_dst = output_dir / ".env.example"
    if env_example_src.exists():
        shutil.copy2(env_example_src, env_example_dst)
        print(f"✓ Copied .env.example")

    # Create runtime directories
    (output_dir / "logs").mkdir(parents=True, exist_ok=True)
    (output_dir / "dialogs").mkdir(parents=True, exist_ok=True)
    (output_dir / "index").mkdir(parents=True, exist_ok=True)
    print("✓ Created runtime directories (logs/, dialogs/, index/)")


def clean_output(output_dir: Path) -> None:
    """Remove previous build output."""
    if output_dir.exists():
        print(f"\nCleaning {output_dir}...")
        # Remove .exe files but keep runtime data
        for exe in output_dir.glob("*.exe"):
            exe.unlink()
            print(f"  Removed {exe.name}")
        # Remove pyinstaller work files
        work_dir = output_dir.parent / "__pycache__" / "pyinstaller"
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)


# ── Main ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Build AgentCanvas CLI executables with PyInstaller",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=str(DEFAULT_OUTPUT),
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean previous build artifacts before building",
    )
    parser.add_argument(
        "--skip-cli",
        action="store_true",
        help="Skip building cli.exe (build mcp.exe only)",
    )
    parser.add_argument(
        "--skip-mcp",
        action="store_true",
        help="Skip building mcp.exe (build cli.exe only)",
    )
    parser.add_argument(
        "--copy-only",
        action="store_true",
        help="Only copy assets, skip PyInstaller build",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    work_dir = HERE

    print(f"AgentCanvas Build Script")
    print(f"{'='*60}")
    print(f"Source:     {work_dir}")
    print(f"Output:     {output_dir}")
    print(f"Clean:      {args.clean}")
    print(f"{'='*60}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean if requested
    if args.clean:
        clean_output(output_dir)

    # Copy assets regardless
    copy_assets(output_dir, work_dir)

    if args.copy_only:
        print("\n✓ Copy-only mode: assets copied, skipping PyInstaller build.")
        return

    # Build executables
    success = True

    if not args.skip_cli:
        ok = build_exe(
            script_name="main.py",
            exe_name="cli",
            work_dir=work_dir,
            output_dir=output_dir,
            console=True,  # cli.exe has console for debug interaction
        )
        success = success and ok
    else:
        print("\n⏭ Skipping cli.exe")

    if not args.skip_mcp:
        ok = build_exe(
            script_name="mcp_server.py",
            exe_name="mcp",
            work_dir=work_dir,
            output_dir=output_dir,
            console=False,  # mcp.exe runs headless via stdio
        )
        success = success and ok
    else:
        print("\n⏭ Skipping mcp.exe")

    # Summary
    print(f"\n{'='*60}")
    if success:
        print("✓ Build complete!")
        print(f"  Output: {output_dir}")
        for exe in output_dir.glob("*.exe"):
            size_mb = exe.stat().st_size / (1024 * 1024)
            print(f"  - {exe.name} ({size_mb:.1f} MB)")
        print(f"  - .env.example")
    else:
        print("✗ Build completed with errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
