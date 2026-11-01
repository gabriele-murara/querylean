"""Third-party license notices for the PyInstaller bundle."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import zipfile
from importlib import metadata
from pathlib import Path

from querylean.app.bundle_resources import BundleResources


class ThirdPartyLicenses:
    """Collects the license of every third-party file in the bundle.

    Each TOC entry (binaries, datas, pure modules, scripts) is attributed to
    its origin, in this order:

    1. the Python distribution that installed the file (dist-info licenses);
    2. QueryLean itself (skipped: its license is ``LICENSE``);
    3. on Linux, the Debian package that owns the file (``dpkg``), whose
       ``/usr/share/doc/<package>/copyright`` lists its licenses;
    4. OpenSSL shipped by the Python interpreter (macOS);
    5. the Python interpreter and its standard library.

    A file with no known origin makes the build fail: a new dependency can
    never be distributed without its license. ``write`` produces
    ``THIRD_PARTY_LICENSES.txt`` and, for GPL components shipped only as
    bytecode, a zip with their source code.
    """

    BUNDLE_DIR = BundleResources.LICENSES_DIR
    OUTPUT_NAME = BundleResources.THIRD_PARTY_LICENSES
    __LICENSE_FILE = re.compile(r"(LICEN[CS]E|COPYING|NOTICE)", re.IGNORECASE)
    __LGPL = ("LGPL-3.0.txt", "GPL-3.0.txt")
    # Distributions that ship no license text in their dist-info.
    __VENDORED = {"pyside6-essentials": __LGPL, "shiboken6": __LGPL}
    __QT_DISTRIBUTIONS = frozenset(__VENDORED)
    # GPL distributions bundled as bytecode: their source ships alongside.
    __SOURCE_ZIP = frozenset({"mysql-connector-python"})
    __ICU = re.compile(r"^libicu")
    __OPENSSL = re.compile(r"^lib(ssl|crypto)[.-]")
    __ZIP_DATE = (1980, 1, 1, 0, 0, 0)
    __WIDTH = 78
    # The project itself: its own license is LICENSE, not a third party.
    __PROJECT = "querylean"

    def __init__(
        self, project_root: Path, vendored_dir: Path, output_dir: Path
    ) -> None:
        self.__project_root = project_root.resolve()
        self.__vendored_dir = vendored_dir
        self.__output_dir = output_dir
        self.__components: dict[str, dict] = {}
        self.__unknown: list[str] = []
        self.__owners = ThirdPartyLicenses.__distribution_owners()
        self.__dpkg_cache: dict[str, str | None] = {}
        self.__has_dpkg = shutil.which("dpkg-query") is not None
        base = {"base": sys.base_prefix, "platbase": sys.base_exec_prefix}
        paths = sysconfig.get_paths(vars=base)
        self.__stdlib = Path(paths["stdlib"]).resolve()
        self.__platstdlib = Path(paths["platstdlib"]).resolve()
        self.__python_prefix = Path(sys.base_prefix).resolve()

    @property
    def components(self) -> dict[str, dict]:
        """Components found so far, by key."""
        return self.__components

    @property
    def unknown(self) -> list[str]:
        """Files whose origin could not be determined."""
        return self.__unknown

    def collect(self, entries: list[tuple]) -> None:
        """Attribute every ``(dest, source, kind)`` TOC entry."""
        self.__add_distribution("pyinstaller")  # bootloader in the executable
        for entry in entries:
            source = entry[1]
            if isinstance(source, str) and os.path.isabs(source):
                self.__classify(entry[0], Path(source))

    def write(self) -> list[tuple[str, str, str]]:
        """Write the notices and return them as PyInstaller DATA entries.

        Raises ``RuntimeError`` when some file has no known license.
        """
        if self.__unknown:
            msg = "Files with no known license (add their origin to {}):\n{}"
            files = "\n".join(sorted(set(self.__unknown)))
            raise RuntimeError(msg.format(Path(__file__).name, files))
        self.__output_dir.mkdir(parents=True, exist_ok=True)
        toc = []
        for component in self.__components.values():
            if component["zip_files"]:
                path = self.__write_source_zip(component)
                component["source"] = "{} (in this package: {}/{})".format(
                    component["source"],
                    ThirdPartyLicenses.BUNDLE_DIR,
                    path.name,
                )
                toc.append(ThirdPartyLicenses.__data_entry(path))
        notices = self.__output_dir / ThirdPartyLicenses.OUTPUT_NAME
        notices.write_text(self.__render(), encoding="utf-8")
        toc.append(ThirdPartyLicenses.__data_entry(notices))
        toc.append(
            ThirdPartyLicenses.__data_entry(self.__project_root / "LICENSE")
        )
        return toc

    # ---------------------------------------------------------- classification
    def __classify(self, dest: str, source: Path) -> None:
        real = source.resolve()
        distribution = self.__owners.get(str(real))
        if distribution == ThirdPartyLicenses.__PROJECT:
            return
        if distribution is not None:
            component = self.__add_distribution(distribution)
            if component["zip_files"] is not None and real.suffix == ".py":
                component["zip_files"].add(real)
            if distribution in ThirdPartyLicenses.__QT_DISTRIBUTIONS and (
                ThirdPartyLicenses.__ICU.match(real.name)
            ):
                self.__add_icu()
            return
        if real.is_relative_to(self.__project_root):
            return  # QueryLean itself
        package = self.__dpkg_owner(source, real)
        if package is not None:
            self.__add_debian_package(package)
        elif ThirdPartyLicenses.__OPENSSL.match(real.name):
            self.__add_openssl()
        elif self.__is_python(real):
            self.__add_python()
        else:
            self.__unknown.append("{} <- {}".format(dest, source))

    def __is_python(self, real: Path) -> bool:
        if real.name.startswith("libpython"):
            return True
        roots = (self.__stdlib, self.__platstdlib, self.__python_prefix)
        return any(real.is_relative_to(root) for root in roots)

    # -------------------------------------------------------------- components
    def __add(self, key: str, **fields: object) -> dict:
        if key not in self.__components:
            component = {"texts": [], "source": None, "zip_files": None}
            component.update(fields)
            self.__components[key] = component
        return self.__components[key]

    def __add_distribution(self, name: str) -> dict:
        key = "python:{}".format(name)
        if key in self.__components:
            return self.__components[key]
        dist = metadata.distribution(name)
        meta = dist.metadata
        label = meta.get("License-Expression") or meta.get("License") or ""
        if not label or "\n" in label or len(label) > 60:
            classifiers = [
                c.split(" :: ")[-1]
                for c in meta.get_all("Classifier") or []
                if c.startswith("License ::")
            ]
            label = "; ".join(classifiers) or "see the license text"
        component = self.__add(
            key,
            name=meta["Name"],
            version=dist.version,
            license=label,
            origin="Python package",
            source="https://pypi.org/project/{}/{}/".format(
                meta["Name"], dist.version
            ),
        )
        for file in sorted(dist.files or [], key=str):
            parts = Path(str(file)).parts
            in_dist_info = any(p.endswith(".dist-info") for p in parts)
            if in_dist_info and ThirdPartyLicenses.__LICENSE_FILE.search(
                parts[-1]
            ):
                path = Path(str(dist.locate_file(file)))
                component["texts"].append((parts[-1], path))
        for text in ThirdPartyLicenses.__VENDORED.get(name, ()):
            component["texts"].append((text, self.__vendored_dir / text))
        if name in ThirdPartyLicenses.__QT_DISTRIBUTIONS:
            component["license"] = "LGPL-3.0-only"
            qt = ".".join(dist.version.split(".")[:2])
            msg = "Qt for Python: https://download.qt.io/official_releases/"
            msg += "QtForPython/pyside6/PySide6-{v}-src/ ; Qt: "
            msg += "https://download.qt.io/official_releases/qt/{qt}/{v}/"
            msg += "single/ . Qt includes third-party code, listed at "
            msg += "https://doc.qt.io/qt-6/licenses-used-in-qt.html"
            component["source"] = msg.format(v=dist.version, qt=qt)
        if name in ThirdPartyLicenses.__SOURCE_ZIP:
            component["zip_files"] = set()
            component["dist"] = dist
        if not component["texts"]:
            self.__unknown.append(
                "{} {}: no license text".format(meta["Name"], dist.version)
            )
        return component

    def __add_icu(self) -> None:
        text = "ICU-73.txt"
        self.__add(
            "icu",
            name="ICU (bundled with Qt)",
            version="73.2",
            license="Unicode-DFS-2016 and ICU",
            origin="part of the PySide6 package",
            texts=[(text, self.__vendored_dir / text)],
        )

    def __add_openssl(self) -> None:
        text = "Apache-2.0.txt"
        self.__add(
            "openssl",
            name="OpenSSL (bundled with Python)",
            version="3",
            license="Apache-2.0",
            origin="Python interpreter",
            texts=[(text, self.__vendored_dir / text)],
            source="https://www.openssl.org/source/",
        )

    def __add_python(self) -> None:
        license_file = self.__stdlib / "LICENSE.txt"
        component = self.__add(
            "python",
            name="Python",
            version=platform.python_version(),
            license="PSF-2.0",
            origin="interpreter and standard library",
            source="https://www.python.org/downloads/source/",
        )
        if not component["texts"]:
            if license_file.is_file():
                component["texts"].append(("LICENSE.txt", license_file))
            else:
                msg = "Python license not found at {}"
                self.__unknown.append(msg.format(license_file))

    def __add_debian_package(self, package: str) -> None:
        key = "deb:{}".format(package)
        if key in self.__components:
            return
        fields = "${Version}\t${source:Package}\t${source:Version}"
        result = subprocess.run(
            ["dpkg-query", "-W", "-f", fields, package],
            capture_output=True,
            text=True,
            check=True,
            env=ThirdPartyLicenses.__c_locale(),
        )
        version, source_name, source_version = result.stdout.split("\t")
        name = package.split(":")[0]
        copyright_file = Path("/usr/share/doc") / name / "copyright"
        component = self.__add(
            key,
            name=name,
            version=version,
            license="see the Debian copyright file",
            origin="Ubuntu/Debian package",
            source="https://launchpad.net/ubuntu/+source/{}/{}".format(
                source_name, source_version
            ),
        )
        if copyright_file.is_file():
            component["texts"].append(("copyright", copyright_file))
        else:
            msg = "{}: missing {}".format(package, copyright_file)
            self.__unknown.append(msg)

    def __dpkg_owner(self, source: Path, real: Path) -> str | None:
        if not self.__has_dpkg:
            return None
        candidates = [str(source), str(real)]
        for path in list(candidates):
            if path.startswith("/lib"):
                candidates.append("/usr{}".format(path))
            elif path.startswith("/usr/lib"):
                candidates.append(path[len("/usr") :])
        for path in candidates:
            if path not in self.__dpkg_cache:
                result = subprocess.run(
                    ["dpkg-query", "-S", path],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=ThirdPartyLicenses.__c_locale(),
                )
                owner = None
                if result.returncode == 0:
                    owner = result.stdout.split(": ")[0].split(", ")[0]
                self.__dpkg_cache[path] = owner
            if self.__dpkg_cache[path] is not None:
                return self.__dpkg_cache[path]
        return None

    # ------------------------------------------------------------------ output
    def __write_source_zip(self, component: dict) -> Path:
        dist = component["dist"]
        base = Path(str(dist.locate_file(""))).resolve()
        name = "{}-{}-source.zip".format(
            component["name"], component["version"]
        )
        path = self.__output_dir / name
        files = sorted(component["zip_files"])
        files += [text for _label, text in component["texts"]]
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                real = Path(file).resolve()
                if real.is_relative_to(base):
                    arcname = real.relative_to(base).as_posix()
                else:
                    arcname = real.name
                info = zipfile.ZipInfo(arcname, ThirdPartyLicenses.__ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, real.read_bytes())
        return path

    def __render(self) -> str:
        width = ThirdPartyLicenses.__WIDTH
        components = sorted(
            self.__components.values(), key=lambda c: c["name"].lower()
        )
        lines = [
            "QueryLean - third-party software",
            "=" * width,
            "",
            "QueryLean is distributed under the MIT License (see LICENSE).",
            "This package also contains the third-party components listed",
            "below. Each one is distributed under its own license, whose full",
            "text follows. The libraries are separate shared objects or",
            "Python modules: they can be replaced with modified versions.",
            "",
            "Components",
            "-" * width,
        ]
        for c in components:
            line = "- {} {}: {} ({})"
            lines.append(
                line.format(c["name"], c["version"], c["license"], c["origin"])
            )
        lines += ["", "Source code", "-" * width]
        for c in components:
            if c["source"]:
                line = "- {} {}: {}"
                lines.append(line.format(c["name"], c["version"], c["source"]))
        lines += ["", "License texts", "=" * width]
        for c in components:
            lines += ["", "#" * width, "{} {}".format(c["name"], c["version"])]
            lines.append("#" * width)
            for label, path in c["texts"]:
                lines += ["", "--- {} ---".format(label), ""]
                text = Path(path).read_text(encoding="utf-8", errors="replace")
                lines.append(text.rstrip())
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def __data_entry(path: Path) -> tuple[str, str, str]:
        dest = "{}/{}".format(ThirdPartyLicenses.BUNDLE_DIR, path.name)
        return (dest, str(path), "DATA")

    @staticmethod
    def __distribution_owners() -> dict[str, str]:
        owners: dict[str, str] = {}
        for dist in metadata.distributions():
            name = dist.metadata["Name"]
            if not name:
                continue
            normalized = re.sub(r"[-_.]+", "-", name).lower()
            for file in dist.files or []:
                path = os.path.realpath(str(dist.locate_file(file)))
                owners.setdefault(path, normalized)
        return owners

    @staticmethod
    def __c_locale() -> dict[str, str]:
        return {**os.environ, "LC_ALL": "C"}
