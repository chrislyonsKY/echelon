"""
Public imagery service for Capella and Maxar open-data catalogs.

This service normalizes scene discovery across the two public catalogs and
provides lightweight raster analysis for analyst workflows. SAR processing uses
windowed raster reads today and exposes a future-ready flag when ``sarkit`` is
available in the runtime.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import urljoin

import httpx
import numpy as np
import rasterio
import rasterio.windows
from dateutil.parser import isoparse
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

logger = logging.getLogger(__name__)

CAPELLA_DATETIME_ROOT = "https://capella-open-data.s3.us-west-2.amazonaws.com/stac/capella-open-data-by-datetime/catalog.json"
MAXAR_EVENTS_ROOT = "https://maxar-opendata.s3.amazonaws.com/events/catalog.json"

_ALLOWED_ITEM_URL_PREFIXES = (
    "https://capella-open-data.s3.us-west-2.amazonaws.com/stac/",
    "https://maxar-opendata.s3.amazonaws.com/events/",
)
_CAPELLA_PRODUCT_PRIORITY = {"GEO": 0, "GEC": 1, "SICD": 2, "SLC": 3}

try:
    import sarkit as _sarkit  # type: ignore[import-not-found]  # noqa: F401

    SARKIT_AVAILABLE = True
except Exception:
    SARKIT_AVAILABLE = False


class OpenImageryService:
    """Normalized scene search and raster analysis for public imagery sources."""

    def search_scenes(
        self,
        provider: str,
        bbox: tuple[float, float, float, float],
        date_from: date,
        date_to: date,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        if provider == "capella":
            return self._search_capella(bbox, date_from, date_to, limit)
        if provider == "maxar":
            return self._search_maxar(bbox, date_from, date_to, limit)
        raise ValueError(f"Unsupported imagery provider: {provider}")

    def analyze_scene(
        self,
        item_url: str,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> dict[str, Any]:
        self._validate_item_url(item_url)
        item = _fetch_json(item_url)
        provider = self._infer_provider(item_url, item)
        analysis_bbox = bbox or _as_bbox(item.get("bbox"))
        if analysis_bbox is None:
            raise ValueError("Scene is missing a usable bbox")

        if provider == "capella":
            return self._analyze_capella(item_url, item, analysis_bbox)
        return self._analyze_maxar(item_url, item, analysis_bbox)

    def _search_capella(
        self,
        bbox: tuple[float, float, float, float],
        date_from: date,
        date_to: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        scenes_by_collect: dict[str, dict[str, Any]] = {}

        for day in _date_range(date_from, date_to):
            day_catalog_url = _capella_day_catalog_url(day)
            try:
                catalog = _fetch_json(day_catalog_url)
            except FileNotFoundError:
                continue

            for link in catalog.get("links", []):
                if link.get("rel") != "item":
                    continue
                item_url = _resolve_url(day_catalog_url, link.get("href", ""))
                if not item_url:
                    continue

                try:
                    item = _fetch_json(item_url)
                except Exception:
                    logger.warning("Capella item fetch failed: %s", item_url, exc_info=True)
                    continue

                item_bbox = _as_bbox(item.get("bbox"))
                captured_at = _parse_dt(item.get("properties", {}).get("datetime"))
                if item_bbox is None or captured_at is None:
                    continue
                if not _bbox_intersects(bbox, item_bbox):
                    continue
                if not (date_from <= captured_at.date() <= date_to):
                    continue

                scene = self._normalize_capella_item(item_url, item)
                collect_id = scene["metadata"].get("collectId") or scene["id"]
                existing = scenes_by_collect.get(collect_id)
                if existing is None or self._capella_product_rank(scene) < self._capella_product_rank(existing):
                    scenes_by_collect[collect_id] = scene

        scenes = sorted(
            scenes_by_collect.values(),
            key=lambda scene: scene.get("capturedAt") or "",
            reverse=True,
        )
        return scenes[:limit]

    def _search_maxar(
        self,
        bbox: tuple[float, float, float, float],
        date_from: date,
        date_to: date,
        limit: int,
    ) -> list[dict[str, Any]]:
        root = _fetch_json(MAXAR_EVENTS_ROOT)
        scenes: list[dict[str, Any]] = []

        for event_link in root.get("links", []):
            if event_link.get("rel") != "child":
                continue
            event_url = _resolve_url(MAXAR_EVENTS_ROOT, event_link.get("href", ""))
            if not event_url:
                continue

            try:
                event_collection = _fetch_json(event_url)
            except Exception:
                logger.warning("Maxar event fetch failed: %s", event_url, exc_info=True)
                continue

            if not _extent_intersects(event_collection.get("extent"), bbox, date_from, date_to):
                continue

            event_title = event_collection.get("title") or event_collection.get("id") or "Maxar Event"

            for acquisition_link in event_collection.get("links", []):
                if acquisition_link.get("rel") != "child":
                    continue
                acquisition_url = _resolve_url(event_url, acquisition_link.get("href", ""))
                if not acquisition_url:
                    continue

                try:
                    acquisition = _fetch_json(acquisition_url)
                except Exception:
                    logger.warning("Maxar acquisition fetch failed: %s", acquisition_url, exc_info=True)
                    continue

                if not _extent_intersects(acquisition.get("extent"), bbox, date_from, date_to):
                    continue

                for item_link in acquisition.get("links", []):
                    if item_link.get("rel") != "item":
                        continue
                    item_url = _resolve_url(acquisition_url, item_link.get("href", ""))
                    if not item_url:
                        continue

                    try:
                        item = _fetch_json(item_url)
                    except Exception:
                        logger.warning("Maxar item fetch failed: %s", item_url, exc_info=True)
                        continue

                    item_bbox = _as_bbox(item.get("bbox"))
                    captured_at = _parse_dt(item.get("properties", {}).get("datetime"))
                    if item_bbox is None or captured_at is None:
                        continue
                    if not _bbox_intersects(bbox, item_bbox):
                        continue
                    if not (date_from <= captured_at.date() <= date_to):
                        continue

                    scenes.append(self._normalize_maxar_item(item_url, item, event_title))
                    if len(scenes) >= limit:
                        return sorted(
                            scenes,
                            key=lambda scene: scene.get("capturedAt") or "",
                            reverse=True,
                        )[:limit]
                    break

        return sorted(
            scenes,
            key=lambda scene: scene.get("capturedAt") or "",
            reverse=True,
        )[:limit]

    def _normalize_capella_item(self, item_url: str, item: dict[str, Any]) -> dict[str, Any]:
        properties = item.get("properties", {})
        assets = item.get("assets", {})
        thumbnail_url = _asset_href(assets, "thumbnail")
        preview_url = _asset_href(assets, "preview")
        data_url = _first_data_asset_href(assets, preferred_keys=("HH", "HV", "VH", "VV"))

        return {
            "id": item.get("id"),
            "provider": "capella",
            "title": item.get("id"),
            "capturedAt": _isoformat_dt(_parse_dt(properties.get("datetime"))),
            "bbox": item.get("bbox"),
            "geometry": item.get("geometry") or _geometry_from_bbox(item.get("bbox")),
            "thumbnailUrl": thumbnail_url,
            "previewUrl": preview_url or thumbnail_url or data_url,
            "assetUrl": data_url,
            "itemUrl": item_url,
            "license": "CC-BY-4.0",
            "metadata": {
                "platform": properties.get("platform"),
                "productType": properties.get("sar:product_type"),
                "instrumentMode": properties.get("sar:instrument_mode"),
                "polarizations": properties.get("sar:polarizations") or [],
                "incidenceAngle": properties.get("view:incidence_angle"),
                "resolutionRange": properties.get("sar:resolution_range"),
                "resolutionAzimuth": properties.get("sar:resolution_azimuth"),
                "observationDirection": properties.get("sar:observation_direction"),
                "collectId": properties.get("capella:collect_id"),
            },
        }

    def _normalize_maxar_item(
        self,
        item_url: str,
        item: dict[str, Any],
        event_title: str,
    ) -> dict[str, Any]:
        properties = item.get("properties", {})
        assets = item.get("assets", {})
        visual_url = _asset_href(assets, "visual")
        analytic_url = _first_data_asset_href(assets, preferred_keys=("ms_analytic", "pan_analytic", "visual"))
        eo_bands = assets.get("ms_analytic", {}).get("eo:bands") or assets.get("visual", {}).get("eo:bands") or []

        return {
            "id": item.get("id"),
            "provider": "maxar",
            "title": event_title,
            "capturedAt": _isoformat_dt(_parse_dt(properties.get("datetime"))),
            "bbox": item.get("bbox"),
            "geometry": item.get("geometry") or _geometry_from_bbox(item.get("bbox")),
            "thumbnailUrl": visual_url,
            "previewUrl": visual_url or analytic_url,
            "assetUrl": analytic_url or visual_url,
            "itemUrl": item_url,
            "license": "CC-BY-NC-4.0",
            "metadata": {
                "eventTitle": event_title,
                "platform": properties.get("platform"),
                "catalogId": properties.get("catalog_id"),
                "gsd": properties.get("gsd"),
                "utmZone": properties.get("utm_zone"),
                "cloudPercent": properties.get("tile:clouds_percent"),
                "bandCount": len(eo_bands),
            },
        }

    def _analyze_capella(
        self,
        item_url: str,
        item: dict[str, Any],
        bbox: tuple[float, float, float, float],
    ) -> dict[str, Any]:
        assets = item.get("assets", {})
        properties = item.get("properties", {})
        data_url = _first_data_asset_href(assets, preferred_keys=("HH", "HV", "VH", "VV"))
        metadata_url = _asset_href(assets, "metadata")

        if not data_url:
            raise ValueError("Capella item has no usable raster asset")

        summary = _summarize_raster_window(data_url, bbox, max_bands=1, classify_sar=True)
        metadata_summary: dict[str, Any] = {
            "productType": properties.get("sar:product_type"),
            "instrumentMode": properties.get("sar:instrument_mode"),
            "polarizations": properties.get("sar:polarizations") or [],
            "incidenceAngle": properties.get("view:incidence_angle"),
            "resolutionRange": properties.get("sar:resolution_range"),
            "resolutionAzimuth": properties.get("sar:resolution_azimuth"),
            "lookAngle": properties.get("capella:look_angle"),
            "observationDirection": properties.get("sar:observation_direction"),
        }

        if metadata_url:
            try:
                extended = _fetch_json(metadata_url)
                metadata_summary["extendedMetadataKeys"] = sorted(extended.keys())[:20]
            except Exception:
                logger.warning("Capella metadata fetch failed: %s", metadata_url, exc_info=True)

        return {
            "provider": "capella",
            "sceneId": item.get("id"),
            "itemUrl": item_url,
            "processor": "rasterio",
            "analysisType": "sar_backscatter",
            "sarkitAvailable": SARKIT_AVAILABLE,
            "metadata": metadata_summary,
            "summary": summary,
        }

    def _analyze_maxar(
        self,
        item_url: str,
        item: dict[str, Any],
        bbox: tuple[float, float, float, float],
    ) -> dict[str, Any]:
        assets = item.get("assets", {})
        properties = item.get("properties", {})
        raster_url = _first_data_asset_href(assets, preferred_keys=("visual", "ms_analytic", "pan_analytic"))
        if not raster_url:
            raise ValueError("Maxar item has no usable raster asset")

        summary = _summarize_raster_window(raster_url, bbox, max_bands=3, classify_sar=False)
        return {
            "provider": "maxar",
            "sceneId": item.get("id"),
            "itemUrl": item_url,
            "processor": "rasterio",
            "analysisType": "optical_scene_summary",
            "sarkitAvailable": False,
            "metadata": {
                "platform": properties.get("platform"),
                "gsd": properties.get("gsd"),
                "catalogId": properties.get("catalog_id"),
                "cloudPercent": properties.get("tile:clouds_percent"),
            },
            "summary": summary,
        }

    def _capella_product_rank(self, scene: dict[str, Any]) -> int:
        product_type = str(scene.get("metadata", {}).get("productType") or "")
        return _CAPELLA_PRODUCT_PRIORITY.get(product_type, 99)

    def _validate_item_url(self, item_url: str) -> None:
        if not item_url.startswith(_ALLOWED_ITEM_URL_PREFIXES):
            raise ValueError("itemUrl must be a Capella or Maxar open-data STAC item URL")

    def _infer_provider(self, item_url: str, item: dict[str, Any]) -> str:
        if "capella-open-data" in item_url or item.get("properties", {}).get("constellation") == "capella":
            return "capella"
        return "maxar"


@lru_cache(maxsize=2048)
def _fetch_json(url: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(url)
        if response.status_code == 404:
            raise FileNotFoundError(url)
        response.raise_for_status()
        return response.json()


def _resolve_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def _asset_href(assets: dict[str, Any], key: str) -> str | None:
    asset = assets.get(key)
    href = asset.get("href") if isinstance(asset, dict) else None
    return href if isinstance(href, str) and href else None


def _first_data_asset_href(
    assets: dict[str, Any],
    preferred_keys: tuple[str, ...],
) -> str | None:
    for key in preferred_keys:
        href = _asset_href(assets, key)
        if href:
            return href

    for key, asset in assets.items():
        if not isinstance(asset, dict):
            continue
        roles = asset.get("roles") or []
        if "data" in roles:
            href = asset.get("href")
            if isinstance(href, str) and href:
                return href
    return None


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return isoparse(value.replace(" ", "T"))
    except Exception:
        return None


def _isoformat_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _as_bbox(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, list) or len(value) < 4:
        return None
    try:
        west, south, east, north = value[:4]
        return float(west), float(south), float(east), float(north)
    except (TypeError, ValueError):
        return None


def _bbox_intersects(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    left_w, left_s, left_e, left_n = left
    right_w, right_s, right_e, right_n = right
    return not (
        left_e < right_w
        or right_e < left_w
        or left_n < right_s
        or right_n < left_s
    )


def _geometry_from_bbox(bbox: Any) -> dict[str, Any] | None:
    normalized = _as_bbox(bbox)
    if normalized is None:
        return None
    west, south, east, north = normalized
    return {
        "type": "Polygon",
        "coordinates": [[
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
        ]],
    }


def _extent_intersects(
    extent: dict[str, Any] | None,
    bbox: tuple[float, float, float, float],
    date_from: date,
    date_to: date,
) -> bool:
    if not extent:
        return True

    spatial_boxes = extent.get("spatial", {}).get("bbox") or []
    if spatial_boxes:
        spatial_match = any(
            _bbox_intersects(bbox, (float(box[0]), float(box[1]), float(box[2]), float(box[3])))
            for box in spatial_boxes
            if isinstance(box, list) and len(box) >= 4
        )
        if not spatial_match:
            return False

    intervals = extent.get("temporal", {}).get("interval") or []
    if intervals:
        temporal_match = False
        for interval in intervals:
            if not isinstance(interval, list) or len(interval) < 2:
                continue
            start = _parse_dt(interval[0]) if interval[0] else None
            end = _parse_dt(interval[1]) if interval[1] else None
            if _date_interval_intersects(start, end, date_from, date_to):
                temporal_match = True
                break
        if not temporal_match:
            return False

    return True


def _date_interval_intersects(
    start: datetime | None,
    end: datetime | None,
    query_start: date,
    query_end: date,
) -> bool:
    start_date = start.date() if start else date.min
    end_date = end.date() if end else date.max
    return not (end_date < query_start or query_end < start_date)


def _date_range(start: date, end: date) -> list[date]:
    current = start
    days: list[date] = []
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


def _capella_day_catalog_url(value: date) -> str:
    year = value.strftime("%Y")
    month = value.strftime("%m")
    day = value.strftime("%Y-%m-%d")
    base = CAPELLA_DATETIME_ROOT.removesuffix("/catalog.json")
    return f"{base}/capella-open-data-{year}/capella-open-data-{year}-{month}/capella-open-data-{day}/catalog.json"


def _summarize_raster_window(
    href: str,
    bbox: tuple[float, float, float, float],
    *,
    max_bands: int,
    classify_sar: bool,
) -> dict[str, Any]:
    west, south, east, north = bbox

    with rasterio.open(href) as src:
        native_bounds = transform_bounds("EPSG:4326", src.crs, west, south, east, north)
        window = from_bounds(*native_bounds, src.transform)
        full_window = rasterio.windows.Window(0, 0, src.width, src.height)
        window = window.intersection(full_window)
        if window.width < 1 or window.height < 1:
            raise ValueError("Requested bbox falls outside the raster footprint")

        target_height = max(1, min(768, int(window.height)))
        target_width = max(1, min(768, int(window.width)))
        band_indexes = list(range(1, min(src.count, max_bands) + 1))

        data = src.read(
            band_indexes,
            window=window,
            out_shape=(len(band_indexes), target_height, target_width),
            resampling=Resampling.average,
        ).astype(np.float32)

        nodata = src.nodata
        if nodata is not None:
            data = np.where(data == nodata, np.nan, data)

        band_summaries = [_band_summary(data[index]) for index in range(data.shape[0])]

        summary: dict[str, Any] = {
            "window": {
                "width": int(target_width),
                "height": int(target_height),
                "bandCount": len(band_indexes),
            },
            "bands": band_summaries,
            "assetHref": href,
        }

        if classify_sar and data.shape[0] >= 1:
            summary["sar"] = _sar_texture_summary(data[0])

        return summary


def _band_summary(band: np.ndarray) -> dict[str, Any]:
    valid = band[np.isfinite(band)]
    if valid.size == 0:
        return {
            "pixelCount": 0,
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "p50": None,
            "p95": None,
        }

    return {
        "pixelCount": int(valid.size),
        "min": float(np.min(valid)),
        "max": float(np.max(valid)),
        "mean": float(np.mean(valid)),
        "std": float(np.std(valid)),
        "p50": float(np.percentile(valid, 50)),
        "p95": float(np.percentile(valid, 95)),
    }


def _sar_texture_summary(band: np.ndarray) -> dict[str, Any]:
    valid = band[np.isfinite(band)]
    if valid.size == 0:
        return {
            "strongScatterFraction": 0.0,
            "edgeFraction": 0.0,
        }

    strong_scatter_threshold = float(np.percentile(valid, 90))
    strong_scatter_fraction = float(np.mean(valid >= strong_scatter_threshold))

    grad_y, grad_x = np.gradient(np.nan_to_num(band, nan=0.0))
    gradient_magnitude = np.hypot(grad_x, grad_y)
    gradient_valid = gradient_magnitude[np.isfinite(gradient_magnitude)]
    edge_threshold = float(np.percentile(gradient_valid, 90)) if gradient_valid.size else 0.0
    edge_fraction = float(np.mean(gradient_valid >= edge_threshold)) if gradient_valid.size else 0.0

    return {
        "strongScatterFraction": strong_scatter_fraction,
        "edgeFraction": edge_fraction,
    }
