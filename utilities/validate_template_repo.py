#!/usr/bin/env python3
"""
meltr template repository validator.

Validates a vendor template repository hierarchy against the JSON schemas in
`schemas/` and reports PASS/WARN/FAIL statuses for each relevant file.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import yaml
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError


STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"


@dataclass
class Result:
    status: str
    path: Path
    message: str = ""

    def format(self, root: Path) -> str:
        rel_path = self.path.relative_to(root) if self.path.is_absolute() else self.path
        msg = f" - {self.message}" if self.message else ""
        return f"{self.status:<5} {rel_path}{msg}"


class SchemaRegistry:
    def __init__(self, schemas_dir: Path) -> None:
        self.schemas_dir = schemas_dir
        self._validators: Dict[str, Draft7Validator] = {}

    def validator(self, name: str) -> Draft7Validator:
        if name not in self._validators:
            schema_path = self.schemas_dir / f"{name}.schema.json"
            try:
                schema_data = json.loads(schema_path.read_text())
            except FileNotFoundError:
                raise RuntimeError(f"Schema file missing: {schema_path}") from None
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Schema file invalid JSON: {schema_path}: {exc}") from exc
            validator = Draft7Validator(schema_data)
            self._validators[name] = validator
        return self._validators[name]


class TemplateRepositoryValidator:
    def __init__(self, templates_root: Path, schemas_dir: Path) -> None:
        self.templates_root = templates_root
        self.schemas = SchemaRegistry(schemas_dir)
        self.results: List[Result] = []

    def validate(self) -> List[Result]:
        if not self.templates_root.exists():
            raise RuntimeError(f"Templates root not found: {self.templates_root}")
        vendor_meta = self.templates_root / "vendor.meta.yaml"
        if vendor_meta.exists():
            self._validate_vendor(self.templates_root)
        else:
            for vendor_dir in sorted(self.templates_root.iterdir()):
                if vendor_dir.is_dir():
                    self._validate_vendor(vendor_dir)
        return self.results

    def _record(self, status: str, path: Path, message: str = "") -> None:
        self.results.append(Result(status=status, path=path.resolve(), message=message))

    def _validate_vendor(self, vendor_dir: Path) -> None:
        vendor_id = vendor_dir.name
        vendor_meta = vendor_dir / "vendor.meta.yaml"
        vendor_data: Optional[dict] = None

        if not vendor_meta.exists():
            self._record(STATUS_FAIL, vendor_meta, "Missing vendor metadata file")
        else:
            vendor_data = self._load_yaml(vendor_meta)
            if vendor_data is None:
                return
            self._validate_against_schema("vendor", vendor_meta, vendor_data)
            schema_vendor = vendor_data.get("vendor")
            if schema_vendor != vendor_id:
                self._record(
                    STATUS_FAIL,
                    vendor_meta,
                    f"'vendor' field '{schema_vendor}' must match directory '{vendor_id}'",
                )
        for product_dir in sorted(p for p in vendor_dir.iterdir() if p.is_dir()):
            self._validate_product(vendor_dir, product_dir, vendor_data)

    def _validate_product(
        self, vendor_dir: Path, product_dir: Path, vendor_data: Optional[dict]
    ) -> None:
        vendor_id = vendor_dir.name
        product_id = product_dir.name

        product_meta = product_dir / "product.meta.yaml"
        product_data: Optional[dict] = None

        if not product_meta.exists():
            self._record(STATUS_FAIL, product_meta, "Missing product metadata file")
        else:
            product_data = self._load_yaml(product_meta)
            if product_data is None:
                product_data = {}
            else:
                self._validate_against_schema("product", product_meta, product_data)
            if product_data.get("vendor") != vendor_id:
                self._record(
                    STATUS_FAIL,
                    product_meta,
                    f"'vendor' field '{product_data.get('vendor')}' must match vendor directory '{vendor_id}'",
                )
            if product_data.get("product") != product_id:
                self._record(
                    STATUS_FAIL,
                    product_meta,
                    f"'product' field '{product_data.get('product')}' must match directory '{product_id}'",
                )

        collection_path = product_dir / "collection.json"
        collection_data: Optional[dict] = None
        if not collection_path.exists():
            self._record(STATUS_FAIL, collection_path, "Missing collection.json")
        else:
            collection_data = self._load_json(collection_path)
            if collection_data is not None:
                self._validate_against_schema("collection", collection_path, collection_data)

        expected_templates: Dict[Tuple[str, str], Path] = {}
        declared_templates: set[Tuple[str, str]] = set()
        if collection_data and isinstance(collection_data.get("templates"), list):
            for entry in collection_data["templates"]:
                if not isinstance(entry, str):
                    self._record(
                        STATUS_FAIL,
                        collection_path,
                        f"Template entry {entry!r} must be string path data_source/template_name",
                    )
                    continue
                if "/" not in entry:
                    self._record(
                        STATUS_FAIL,
                        collection_path,
                        f"Template entry '{entry}' must use 'data_source/template_name' format",
                    )
                    continue
                data_source_name, template_name_raw = entry.split("/", 1)
                template_name = (
                    template_name_raw[:-3]
                    if template_name_raw.endswith(".j2")
                    else template_name_raw
                )
                expected_templates[(data_source_name, template_name)] = product_dir / data_source_name
                declared_templates.add((data_source_name, template_name))

        for (data_source_name, template_name), ds_dir in expected_templates.items():
            data_source_dir = product_dir / data_source_name
            if not data_source_dir.exists():
                self._record(
                    STATUS_FAIL,
                    data_source_dir,
                    f"Data source directory missing for template '{data_source_name}/{template_name}'",
                )
                continue
            self._validate_template(
                vendor_id, product_id, data_source_name, template_name, data_source_dir
            )

        for data_source_dir in sorted(p for p in product_dir.iterdir() if p.is_dir()):
            data_source_name = data_source_dir.name
            for meta_file in sorted(data_source_dir.glob("*.meta.yaml")):
                template_name = self._template_name_from_meta(meta_file)
                key = (data_source_name, template_name)
                if key not in expected_templates:
                    self._record(
                        STATUS_WARN,
                        meta_file,
                        "Template metadata not referenced by collection.json",
                    )
                else:
                    expected_templates.pop(key, None)
            for template_file in sorted(data_source_dir.glob("*.j2")):
                template_name = template_file.stem
                key = (data_source_name, template_name)
                if key not in declared_templates:
                    self._record(
                        STATUS_WARN,
                        template_file,
                        "Template file not referenced by collection.json",
                    )

        for (data_source_name, template_name), _ in expected_templates.items():
            self._record(
                STATUS_FAIL,
                product_dir / data_source_name / f"{template_name}.meta.yaml",
                "Template declared in collection.json but metadata/template files missing",
            )

    def _validate_template(
        self,
        vendor_id: str,
        product_id: str,
        data_source_name: str,
        template_name: str,
        data_source_dir: Path,
    ) -> None:
        meta_path = data_source_dir / f"{template_name}.meta.yaml"
        template_path = data_source_dir / f"{template_name}.j2"

        if not template_path.exists():
            self._record(
                STATUS_FAIL,
                template_path,
                "Template file missing",
            )
        else:
            self._record(STATUS_PASS, template_path)

        if not meta_path.exists():
            self._record(
                STATUS_FAIL,
                meta_path,
                "Template metadata missing",
            )
            return

        meta_data = self._load_yaml(meta_path)
        if meta_data is None:
            return
        self._validate_against_schema("template", meta_path, meta_data)

        if meta_data.get("vendor") != vendor_id:
            self._record(
                STATUS_FAIL,
                meta_path,
                f"'vendor' field '{meta_data.get('vendor')}' must match vendor directory '{vendor_id}'",
            )
        if meta_data.get("product") != product_id:
            self._record(
                STATUS_FAIL,
                meta_path,
                f"'product' field '{meta_data.get('product')}' must match product directory '{product_id}'",
            )
        if meta_data.get("data_source") != data_source_name:
            self._record(
                STATUS_FAIL,
                meta_path,
                f"'data_source' field '{meta_data.get('data_source')}' must match data source directory '{data_source_name}'",
            )

    def _validate_against_schema(self, schema_name: str, path: Path, data: dict) -> None:
        try:
            validator = self.schemas.validator(schema_name)
        except RuntimeError as exc:
            self._record(STATUS_FAIL, path, str(exc))
            return

        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            for err in errors:
                location = "/".join(str(p) for p in err.absolute_path) or "<root>"
                self._record(
                    STATUS_FAIL,
                    path,
                    f"{location}: {err.message}",
                )
        else:
            self._record(STATUS_PASS, path)

    def _load_yaml(self, path: Path) -> Optional[dict]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except FileNotFoundError:
            self._record(STATUS_FAIL, path, "File not found")
            return None
        except yaml.YAMLError as exc:
            self._record(STATUS_FAIL, path, f"YAML parse error: {exc}")
            return None
        if not isinstance(data, dict):
            self._record(STATUS_FAIL, path, "YAML root must be a mapping/object")
            return None
        return data

    def _load_json(self, path: Path) -> Optional[dict]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            self._record(STATUS_FAIL, path, "File not found")
            return None
        except json.JSONDecodeError as exc:
            self._record(STATUS_FAIL, path, f"JSON parse error: {exc}")
            return None
        if not isinstance(data, dict):
            self._record(STATUS_FAIL, path, "JSON root must be an object")
            return None
        return data

    @staticmethod
    def _template_name_from_meta(path: Path) -> str:
        name = path.name
        if name.endswith(".meta.yaml"):
            return name[: -len(".meta.yaml")]
        return path.stem


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a meltr vendor template repository structure."
    )
    parser.add_argument(
        "templates_root",
        nargs="?",
        type=Path,
        default=Path("examples/templates"),
        help="Path to the templates root (default: examples/templates)",
    )
    parser.add_argument(
        "--schemas",
        type=Path,
        default=Path("schemas"),
        help="Path to schema directory (default: schemas)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    templates_root = args.templates_root.resolve()
    schemas_dir = args.schemas.resolve()

    validator = TemplateRepositoryValidator(templates_root, schemas_dir)
    try:
        results = validator.validate()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = {STATUS_PASS: 0, STATUS_WARN: 0, STATUS_FAIL: 0}
    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
        print(result.format(templates_root))

    print(
        "\nSummary: "
        f"{summary[STATUS_PASS]} pass, "
        f"{summary[STATUS_WARN]} warn, "
        f"{summary[STATUS_FAIL]} fail"
    )
    return 0 if summary[STATUS_FAIL] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

