from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import shapefile


ROOT = Path(__file__).resolve().parents[1]
ASSET_JSON = ROOT / "web" / "public" / "globe-data" / "natural-earth-110m.json"
SOURCE_JSON = ROOT / "web" / "public" / "globe-data" / "natural-earth-110m-source.json"
DEFAULT_COUNTRIES_ZIP = Path(tempfile.gettempdir()) / "ne_110m_admin_0_countries.zip"
SCRATCH_DIR = ROOT / ".tmp_ne_admin0"
COUNTRIES_SOURCE_PAGE = (
    "https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/"
)
COUNTRIES_DOWNLOAD_URL = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
WORLDVIEW_NOTE = (
    "Natural Earth admin boundaries are de facto reference geometry and must not be presented as "
    "de jure sovereignty claims."
)
ROUND_DIGITS = 3


def _slug(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "-":
            chars.append("-")
    return "".join(chars).strip("-") or "country"


def _round_point(point: list[float] | tuple[float, float]) -> list[float]:
    return [round(float(point[0]), ROUND_DIGITS), round(float(point[1]), ROUND_DIGITS)]


def _shape_rings(shape: shapefile.Shape) -> list[list[list[float]]]:
    if shape.shapeType not in {
        shapefile.POLYGON,
        shapefile.POLYGONM,
        shapefile.POLYGONZ,
    }:
        return []
    parts = list(shape.parts) + [len(shape.points)]
    rings: list[list[list[float]]] = []
    for index in range(len(parts) - 1):
        start = parts[index]
        end = parts[index + 1]
        ring = [_round_point(point) for point in shape.points[start:end]]
        if len(ring) >= 3:
            rings.append(ring)
    return rings


def _read_country_features(zip_path: Path) -> list[dict[str, Any]]:
    extract_root = SCRATCH_DIR
    shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member_name in archive.namelist():
                suffix = Path(member_name).suffix.lower()
                if suffix not in {".cpg", ".dbf", ".prj", ".shp", ".shx"}:
                    continue
                target_path = extract_root / Path(member_name).name
                target_path.write_bytes(archive.read(member_name))
        shp_path = next(extract_root.glob("*.shp"), None)
        if shp_path is None:
            raise FileNotFoundError(f"No .shp file found inside {zip_path}")

        reader = shapefile.Reader(str(shp_path))
        field_names = [field[0] for field in reader.fields[1:]]
        features: list[dict[str, Any]] = []
        for shape_record in reader.iterShapeRecords():
            rings = _shape_rings(shape_record.shape)
            if not rings:
                continue
            properties = dict(zip(field_names, shape_record.record))
            name = str(
                properties.get("NAME_EN")
                or properties.get("NAME")
                or properties.get("ADMIN")
                or properties.get("SOVEREIGNT")
                or "Unknown"
            ).strip()
            iso_a3 = str(
                properties.get("ADM0_A3")
                or properties.get("SOV_A3")
                or properties.get("ISO_A3_EH")
                or ""
            ).strip()
            if iso_a3 == "-99":
                iso_a3 = ""
            feature_id = iso_a3 or _slug(name)
            features.append(
                {
                    "id": feature_id,
                    "iso_a3": iso_a3,
                    "name": name,
                    "rings": rings,
                }
            )
        return features
    finally:
        shutil.rmtree(extract_root, ignore_errors=True)


def build_asset(countries_zip: Path, asset_json: Path = ASSET_JSON, source_json: Path = SOURCE_JSON) -> None:
    if not countries_zip.exists():
        raise FileNotFoundError(f"Natural Earth countries zip not found: {countries_zip}")
    asset = json.loads(asset_json.read_text(encoding="utf-8"))
    source = json.loads(source_json.read_text(encoding="utf-8"))

    country_features = _read_country_features(countries_zip)
    generated_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    asset_source = asset.get("source", {})
    asset_source.update(
        {
            "dataset": "1:110m Physical + Cultural Vectors",
            "country_url": COUNTRIES_DOWNLOAD_URL,
            "country_source_page": COUNTRIES_SOURCE_PAGE,
            "generated_utc": generated_utc,
            "country_feature_count": len(country_features),
            "worldview_note": WORLDVIEW_NOTE,
        }
    )
    asset["source"] = asset_source
    asset["country_features"] = country_features

    downloads = dict(source.get("downloads", {}))
    downloads["countries"] = COUNTRIES_DOWNLOAD_URL
    source.update(
        {
            "dataset": "1:110m Physical + Cultural Vectors",
            "source_page": COUNTRIES_SOURCE_PAGE,
            "downloads": downloads,
            "note": (
                "Local globe context asset generated from official Natural Earth land, coastline, "
                "and admin-0 country shapefiles. Rounded to 3 decimal places for compact client delivery."
            ),
            "worldview_note": WORLDVIEW_NOTE,
            "generated_utc": generated_utc,
        }
    )

    asset_json.write_text(json.dumps(asset, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    source_json.write_text(json.dumps(source, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Augment the local Natural Earth globe context asset with reviewed admin-0 country geometry."
    )
    parser.add_argument(
        "--countries-zip",
        type=Path,
        default=DEFAULT_COUNTRIES_ZIP,
        help="Path to the official Natural Earth admin-0 countries zip archive.",
    )
    parser.add_argument(
        "--asset-json",
        type=Path,
        default=ASSET_JSON,
        help="Path to the local globe context JSON asset.",
    )
    parser.add_argument(
        "--source-json",
        type=Path,
        default=SOURCE_JSON,
        help="Path to the globe context source metadata JSON.",
    )
    args = parser.parse_args()
    build_asset(countries_zip=args.countries_zip, asset_json=args.asset_json, source_json=args.source_json)
    print(f"Updated globe context asset -> {args.asset_json.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
