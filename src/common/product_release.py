"""
Product Release Module

Provides release management, version management, release notes generation,
and package building for productized release preparation.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ReleaseError(Exception):
    """Base exception for release-related errors."""
    pass


class VersionError(ReleaseError):
    """Exception for version-related errors."""
    pass


class ChecklistError(ReleaseError):
    """Exception for checklist validation errors."""
    pass


class ReleaseType(str, Enum):
    """Types of releases."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    PRE = "pre"
    BUILD = "build"


@dataclass
class ChecklistItem:
    """Single checklist item."""
    name: str
    description: str
    required: bool = True
    checked: bool = False
    category: str = "general"


@dataclass
class ReleaseConfig:
    """Configuration for a release."""
    name: str
    version: str
    release_date: Optional[str] = None
    author: str = ""
    description: str = ""
    changelog_path: Optional[str] = None
    output_dir: str = "dist"
    categories: List[str] = field(default_factory=lambda: [
        "general", "testing", "documentation", "security", "packaging"
    ])


class VersionManager:
    """Manages semantic versioning (SemVer 2.0.0)."""

    SEMVER_PATTERN = re.compile(
        r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
        r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )

    def __init__(self, version: str):
        self._version = version
        self._parts = self._parse(version)

    def _parse(self, version: str) -> Dict[str, Any]:
        match = self.SEMVER_PATTERN.match(version)
        if not match:
            raise VersionError(f"Invalid semantic version: {version}")
        return {
            "major": int(match.group("major")),
            "minor": int(match.group("minor")),
            "patch": int(match.group("patch")),
            "prerelease": match.group("prerelease"),
            "buildmetadata": match.group("buildmetadata"),
        }

    @property
    def version(self) -> str:
        return self._version

    @property
    def major(self) -> int:
        return self._parts["major"]

    @property
    def minor(self) -> int:
        return self._parts["minor"]

    @property
    def patch(self) -> int:
        return self._parts["patch"]

    @property
    def prerelease(self) -> Optional[str]:
        return self._parts["prerelease"]

    @property
    def buildmetadata(self) -> Optional[str]:
        return self._parts["buildmetadata"]

    def bump(self, release_type: ReleaseType, prerelease_id: Optional[str] = None) -> "VersionManager":
        """Bump version according to release type."""
        major, minor, patch = self.major, self.minor, self.patch
        pre = self.prerelease
        build = self.buildmetadata

        if release_type == ReleaseType.MAJOR:
            major += 1
            minor = 0
            patch = 0
            pre = None
            build = None
        elif release_type == ReleaseType.MINOR:
            minor += 1
            patch = 0
            pre = None
            build = None
        elif release_type == ReleaseType.PATCH:
            patch += 1
            pre = None
            build = None
        elif release_type == ReleaseType.PRE:
            if pre and prerelease_id:
                parts = pre.split(".")
                if parts[0] == prerelease_id:
                    try:
                        num = int(parts[-1])
                        parts[-1] = str(num + 1)
                    except ValueError:
                        parts.append("1")
                else:
                    parts = [prerelease_id, "1"]
                pre = ".".join(parts)
            elif prerelease_id:
                pre = f"{prerelease_id}.1"
            else:
                pre = "alpha.1"
        elif release_type == ReleaseType.BUILD:
            build = prerelease_id or f"build.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

        new_version = f"{major}.{minor}.{patch}"
        if pre:
            new_version += f"-{pre}"
        if build:
            new_version += f"+{build}"

        return VersionManager(new_version)

    def is_prerelease(self) -> bool:
        return self.prerelease is not None

    def is_stable(self) -> bool:
        return self.prerelease is None and self.buildmetadata is None

    def compare(self, other: "VersionManager") -> int:
        """Compare two versions. Returns -1, 0, or 1."""
        for key in ("major", "minor", "patch"):
            if self._parts[key] < other._parts[key]:
                return -1
            if self._parts[key] > other._parts[key]:
                return 1

        pre_a = self.prerelease
        pre_b = other.prerelease

        if pre_a is None and pre_b is None:
            return 0
        if pre_a is None:
            return 1
        if pre_b is None:
            return -1

        parts_a = pre_a.split(".")
        parts_b = pre_b.split(".")

        for a, b in zip(parts_a, parts_b):
            is_num_a = a.isdigit()
            is_num_b = b.isdigit()
            if is_num_a and is_num_b:
                ia, ib = int(a), int(b)
                if ia != ib:
                    return -1 if ia < ib else 1
            elif is_num_a:
                return -1
            elif is_num_b:
                return 1
            else:
                if a != b:
                    return -1 if a < b else 1

        if len(parts_a) < len(parts_b):
            return -1
        if len(parts_a) > len(parts_b):
            return 1
        return 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionManager):
            return NotImplemented
        return self.compare(other) == 0

    def __lt__(self, other: "VersionManager") -> bool:
        return self.compare(other) < 0

    def __le__(self, other: "VersionManager") -> bool:
        return self.compare(other) <= 0

    def __gt__(self, other: "VersionManager") -> bool:
        return self.compare(other) > 0

    def __ge__(self, other: "VersionManager") -> bool:
        return self.compare(other) >= 0

    def __repr__(self) -> str:
        return f"VersionManager({self._version!r})"

    def __str__(self) -> str:
        return self._version


class ReleaseNotes:
    """Generates release notes from commits, changelog, or manual entries."""

    def __init__(self, config: ReleaseConfig):
        self.config = config
        self.entries: Dict[str, List[str]] = {}
        self.metadata: Dict[str, Any] = {}

    def add_entry(self, category: str, text: str) -> None:
        """Add a release note entry."""
        if category not in self.entries:
            self.entries[category] = []
        self.entries[category].append(text)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata for release notes."""
        self.metadata[key] = value

    def load_from_changelog(self, path: Optional[str] = None) -> None:
        """Load entries from a changelog file if it exists."""
        changelog = path or self.config.changelog_path
        if not changelog or not os.path.exists(changelog):
            return
        with open(changelog, "r", encoding="utf-8") as f:
            content = f.read()
        # Simple parser: look for version sections
        pattern = re.compile(
            rf"## \[?{re.escape(self.config.version)}\]?.*?\n(.*?)(?=\n## |\Z)",
            re.S,
        )
        match = pattern.search(content)
        if match:
            section = match.group(1)
            current_category = "general"
            for line in section.strip().splitlines():
                line = line.strip()
                if line.startswith("### "):
                    current_category = line[4:].strip().lower()
                elif line.startswith("- "):
                    self.add_entry(current_category, line[2:])

    def generate(self, format_type: str = "markdown") -> str:
        """Generate release notes in specified format."""
        if format_type == "markdown":
            return self._generate_markdown()
        if format_type == "json":
            return self._generate_json()
        if format_type == "txt":
            return self._generate_txt()
        raise ReleaseError(f"Unsupported format: {format_type}")

    def _generate_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# Release {self.config.version}")
        lines.append("")
        if self.config.release_date:
            lines.append(f"**Release Date:** {self.config.release_date}")
        if self.config.author:
            lines.append(f"**Author:** {self.config.author}")
        if self.config.description:
            lines.append(f"**Description:** {self.config.description}")
        lines.append("")

        for category in sorted(self.entries.keys()):
            entries = self.entries[category]
            if not entries:
                continue
            lines.append(f"## {category.capitalize()}")
            for entry in entries:
                lines.append(f"- {entry}")
            lines.append("")

        return "\n".join(lines)

    def _generate_json(self) -> str:
        data = {
            "version": self.config.version,
            "release_date": self.config.release_date,
            "author": self.config.author,
            "description": self.config.description,
            "entries": self.entries,
            "metadata": self.metadata,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _generate_txt(self) -> str:
        lines: List[str] = []
        lines.append(f"Release {self.config.version}")
        lines.append("=" * 40)
        if self.config.release_date:
            lines.append(f"Date: {self.config.release_date}")
        if self.config.author:
            lines.append(f"Author: {self.config.author}")
        lines.append("")
        for category in sorted(self.entries.keys()):
            entries = self.entries[category]
            if not entries:
                continue
            lines.append(f"[{category.capitalize()}]")
            for entry in entries:
                lines.append(f"  - {entry}")
            lines.append("")
        return "\n".join(lines)

    def save(self, path: str, format_type: str = "markdown") -> None:
        """Save release notes to file."""
        content = self.generate(format_type)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


class PackageBuilder:
    """Builds distribution packages."""

    def __init__(self, config: ReleaseConfig):
        self.config = config
        self.source_paths: List[str] = []
        self.exclude_patterns: List[str] = [
            "*.pyc", "__pycache__", ".git", ".gitignore",
            ".env", "*.egg-info", ".pytest_cache", ".mypy_cache"
        ]

    def add_source(self, path: str) -> None:
        """Add a source path to include in the package."""
        self.source_paths.append(path)

    def add_exclude(self, pattern: str) -> None:
        """Add an exclude pattern."""
        self.exclude_patterns.append(pattern)

    def _should_exclude(self, name: str) -> bool:
        for pattern in self.exclude_patterns:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
        return False

    def build_zip(self, output_name: Optional[str] = None) -> str:
        """Build a ZIP package."""
        name = output_name or f"{self.config.name}-{self.config.version}.zip"
        output_path = os.path.join(self.config.output_dir, name)
        os.makedirs(self.config.output_dir, exist_ok=True)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for src in self.source_paths:
                if os.path.isfile(src):
                    arcname = os.path.basename(src)
                    zf.write(src, arcname)
                elif os.path.isdir(src):
                    for root, dirs, files in os.walk(src):
                        dirs[:] = [d for d in dirs if not self._should_exclude(d)]
                        for file in files:
                            if self._should_exclude(file):
                                continue
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, start=os.path.dirname(src))
                            zf.write(full_path, arcname)
        return output_path

    def build_tar(self, output_name: Optional[str] = None, compression: str = "gz") -> str:
        """Build a TAR package with optional compression."""
        ext = f".tar.{compression}" if compression else ".tar"
        name = output_name or f"{self.config.name}-{self.config.version}{ext}"
        output_path = os.path.join(self.config.output_dir, name)
        os.makedirs(self.config.output_dir, exist_ok=True)

        mode = f"w:{compression}" if compression else "w"
        with tarfile.open(output_path, mode) as tf:
            for src in self.source_paths:
                if os.path.isfile(src):
                    arcname = os.path.basename(src)
                    tf.add(src, arcname)
                elif os.path.isdir(src):
                    for root, dirs, files in os.walk(src):
                        dirs[:] = [d for d in dirs if not self._should_exclude(d)]
                        for file in files:
                            if self._should_exclude(file):
                                continue
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, start=os.path.dirname(src))
                            tf.add(full_path, arcname)
        return output_path

    def build_wheel(self, output_name: Optional[str] = None) -> str:
        """Build a Python wheel package using setuptools if available."""
        if not os.path.exists("setup.py") and not os.path.exists("pyproject.toml"):
            raise ReleaseError("No setup.py or pyproject.toml found for wheel build")
        try:
            subprocess.run(
                ["python", "-m", "build", "--wheel", "-o", self.config.output_dir],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError:
            raise ReleaseError("python -m build not available; install build package")
        except subprocess.CalledProcessError as e:
            raise ReleaseError(f"Wheel build failed: {e.stderr.decode()}")

        # Find the built wheel
        wheels = [
            f for f in os.listdir(self.config.output_dir)
            if f.endswith(".whl")
        ]
        if not wheels:
            raise ReleaseError("Wheel file not found after build")
        return os.path.join(self.config.output_dir, sorted(wheels)[-1])


class ReleaseManager:
    """Manages the full release process."""

    DEFAULT_CHECKLIST: List[ChecklistItem] = [
        ChecklistItem("version_bump", "版本号已正确升级", True, False, "general"),
        ChecklistItem("changelog_update", "变更日志已更新", True, False, "documentation"),
        ChecklistItem("tests_pass", "所有测试已通过", True, False, "testing"),
        ChecklistItem("code_review", "代码审查已完成", True, False, "general"),
        ChecklistItem("docs_complete", "文档已完善", True, False, "documentation"),
        ChecklistItem("security_scan", "安全扫描已通过", True, False, "security"),
        ChecklistItem("license_check", "许可证检查已通过", False, False, "general"),
        ChecklistItem("package_build", "包构建成功", True, False, "packaging"),
        ChecklistItem("release_notes", "发布说明已生成", True, False, "documentation"),
        ChecklistItem("git_tag", "Git标签已创建", False, False, "general"),
    ]

    def __init__(self, config: ReleaseConfig):
        self.config = config
        self.version_manager = VersionManager(config.version)
        self.release_notes = ReleaseNotes(config)
        self.package_builder = PackageBuilder(config)
        self._checklist: List[ChecklistItem] = [
            ChecklistItem(
                item.name,
                item.description,
                item.required,
                item.checked,
                item.category,
            )
            for item in self.DEFAULT_CHECKLIST
        ]

    @property
    def checklist(self) -> List[ChecklistItem]:
        return self._checklist

    def add_checklist_item(
        self,
        name: str,
        description: str,
        required: bool = True,
        checked: bool = False,
        category: str = "general",
    ) -> None:
        """Add a custom checklist item."""
        self._checklist.append(
            ChecklistItem(name, description, required, checked, category)
        )

    def check_item(self, name: str, checked: bool = True) -> None:
        """Mark a checklist item as checked or unchecked."""
        for item in self._checklist:
            if item.name == name:
                item.checked = checked
                return
        raise ChecklistError(f"Checklist item not found: {name}")

    def validate_checklist(self) -> Tuple[bool, List[str]]:
        """Validate the checklist. Returns (is_valid, list_of_errors)."""
        errors: List[str] = []
        for item in self._checklist:
            if item.required and not item.checked:
                errors.append(f"Required checklist item not checked: {item.name} ({item.description})")
        return (len(errors) == 0, errors)

    def get_checklist_status(self) -> Dict[str, Any]:
        """Get the current checklist status."""
        total = len(self._checklist)
        checked = sum(1 for item in self._checklist if item.checked)
        required = sum(1 for item in self._checklist if item.required)
        required_checked = sum(
            1 for item in self._checklist if item.required and item.checked
        )
        return {
            "total": total,
            "checked": checked,
            "required": required,
            "required_checked": required_checked,
            "percentage": round(checked / total * 100, 2) if total else 0,
            "items": [
                {
                    "name": item.name,
                    "description": item.description,
                    "required": item.required,
                    "checked": item.checked,
                    "category": item.category,
                }
                for item in self._checklist
            ],
        }

    def prepare_release(
        self,
        release_type: ReleaseType,
        prerelease_id: Optional[str] = None,
    ) -> "ReleaseManager":
        """Prepare a new release by bumping version and resetting checklist."""
        new_version = self.version_manager.bump(release_type, prerelease_id)
        self.version_manager = new_version
        self.config.version = str(new_version)
        self.release_notes = ReleaseNotes(self.config)
        for item in self._checklist:
            item.checked = False
        return self

    def run_release_pipeline(
        self,
        source_paths: List[str],
        notes_entries: Optional[Dict[str, List[str]]] = None,
        package_format: str = "zip",
    ) -> Dict[str, Any]:
        """Run the full release pipeline."""
        # Validate checklist
        valid, errors = self.validate_checklist()
        if not valid:
            raise ChecklistError(f"Release checklist validation failed: {errors}")

        # Add release notes entries
        if notes_entries:
            for category, entries in notes_entries.items():
                for entry in entries:
                    self.release_notes.add_entry(category, entry)

        # Build package
        for src in source_paths:
            self.package_builder.add_source(src)

        if package_format == "zip":
            package_path = self.package_builder.build_zip()
        elif package_format == "tar":
            package_path = self.package_builder.build_tar()
        elif package_format == "tar.gz":
            package_path = self.package_builder.build_tar(compression="gz")
        elif package_format == "tar.bz2":
            package_path = self.package_builder.build_tar(compression="bz2")
        elif package_format == "wheel":
            package_path = self.package_builder.build_wheel()
        else:
            raise ReleaseError(f"Unsupported package format: {package_format}")

        # Generate release notes
        notes_path = os.path.join(
            self.config.output_dir,
            f"RELEASE_NOTES_{self.config.version}.md",
        )
        self.release_notes.save(notes_path, format_type="markdown")

        return {
            "version": self.config.version,
            "package_path": package_path,
            "notes_path": notes_path,
            "checklist_status": self.get_checklist_status(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize release manager state to dict."""
        return {
            "config": {
                "name": self.config.name,
                "version": self.config.version,
                "release_date": self.config.release_date,
                "author": self.config.author,
                "description": self.config.description,
                "output_dir": self.config.output_dir,
            },
            "checklist": self.get_checklist_status(),
        }

    def save_state(self, path: str) -> None:
        """Save release manager state to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
