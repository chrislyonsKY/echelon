"""
Element84 Earth Search STAC client + Sentinel-2 NBR computation.

Scene discovery: pystac-client against Element84 Earth Search (no auth).
Change detection: rasterio windowed COG reads for NBR delta computation.
See: https://earth-search.aws.element84.com/v1
"""
import logging
from datetime import date
from typing import Any

import numpy as np
import rasterio
import rasterio.windows
from rasterio.windows import from_bounds
from pystac_client import Client

logger = logging.getLogger(__name__)

EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"
SENTINEL2_COLLECTION = "sentinel-2-l2a"
MAX_CLOUD_COVER_DEFAULT = 20.0

# NBR delta threshold — values above this indicate significant disturbance
NBR_ANOMALY_THRESHOLD = 0.1

# Sentinel-2 asset keys for the bands we need
ASSET_NIR = "nir"      # B08 (842nm)
ASSET_SWIR = "swir16"  # B11 (1610nm)


class STACService:
    """Client for Element84 Earth Search STAC — Sentinel-2 scene discovery and NBR computation."""

    def __init__(self) -> None:
        self._client = Client.from_file(EARTH_SEARCH_URL)

    def search_scenes(
        self,
        bbox: tuple[float, float, float, float],
        date_from: date,
        date_to: date,
        cloud_cover_max: float = MAX_CLOUD_COVER_DEFAULT,
        max_items: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for Sentinel-2 scenes matching criteria.

        Args:
            bbox: (west, south, east, north) in WGS84.
            date_from: Inclusive start date.
            date_to: Inclusive end date.
            cloud_cover_max: Maximum cloud cover percentage (0-100).
            max_items: Maximum scenes to return.

        Returns:
            List of STAC item dicts with asset hrefs.
        """
        datetime_range = f"{date_from.isoformat()}/{date_to.isoformat()}"

        search = self._client.search(
            collections=[SENTINEL2_COLLECTION],
            bbox=list(bbox),
            datetime=datetime_range,
            query={"eo:cloud_cover": {"lte": cloud_cover_max}},
            max_items=max_items,
            sortby=["-properties.datetime"],
        )

        items = []
        for item in search.items():
            assets = {}
            for key in (ASSET_NIR, ASSET_SWIR, "red", "thumbnail"):
                if key in item.assets:
                    assets[key] = item.assets[key].href

            items.append({
                "id": item.id,
                "datetime": item.datetime.isoformat() if item.datetime else None,
                "bbox": list(item.bbox) if item.bbox else None,
                "cloud_cover": item.properties.get("eo:cloud_cover"),
                "assets": assets,
                "properties": {
                    "platform": item.properties.get("platform"),
                    "grid_square": item.properties.get("s2:mgrs_tile"),
                },
            })

        logger.info(
            "STAC: found %d Sentinel-2 scenes for bbox=%s, dates=%s, cloud<=%s%%",
            len(items), bbox, datetime_range, cloud_cover_max,
        )
        return items

    def compute_nbr_delta(
        self,
        scene_current: dict[str, Any],
        scene_baseline: dict[str, Any],
        bbox: tuple[float, float, float, float],
    ) -> dict[str, Any] | None:
        """Compute Normalized Burn Ratio delta between two scenes for an AOI.

        NBR = (NIR - SWIR) / (NIR + SWIR) using B08 and B11.
        Delta NBR > 0.1 indicates significant disturbance.

        IMPORTANT: Uses windowed reads — never loads full scenes into memory.

        Args:
            scene_current: Current period STAC item dict with asset hrefs.
            scene_baseline: Prior year same-season STAC item dict.
            bbox: AOI bounding box for windowed COG read (west, south, east, north).

        Returns:
            Dict with mean_delta, max_delta, anomaly_pixels, total_pixels,
            or None if computation fails.
        """
        try:
            nbr_current = self._read_nbr_window(scene_current, bbox)
            nbr_baseline = self._read_nbr_window(scene_baseline, bbox)

            if nbr_current is None or nbr_baseline is None:
                return None

            # Compute delta NBR (positive = disturbance/loss)
            delta = nbr_baseline - nbr_current

            # Mask no-data pixels
            valid = np.isfinite(delta)
            if not np.any(valid):
                return None

            delta_valid = delta[valid]
            anomaly_mask = delta_valid > NBR_ANOMALY_THRESHOLD
            anomaly_count = int(np.sum(anomaly_mask))
            total_count = int(np.sum(valid))

            result = {
                "mean_delta": float(np.mean(delta_valid)),
                "max_delta": float(np.max(delta_valid)),
                "anomaly_pixels": anomaly_count,
                "total_pixels": total_count,
                "anomaly_fraction": anomaly_count / total_count if total_count > 0 else 0,
                "is_anomaly": anomaly_count > 0 and (anomaly_count / total_count) > 0.01,
            }

            logger.info(
                "NBR delta: mean=%.4f, max=%.4f, anomaly_px=%d/%d (%.1f%%)",
                result["mean_delta"], result["max_delta"],
                anomaly_count, total_count,
                result["anomaly_fraction"] * 100,
            )
            return result

        except Exception:
            logger.warning("NBR delta computation failed", exc_info=True)
            return None

    def _read_nbr_window(
        self,
        scene: dict[str, Any],
        bbox: tuple[float, float, float, float],
    ) -> np.ndarray | None:
        """Read NIR and SWIR bands from a COG and compute NBR for a bbox window.

        Args:
            scene: STAC item dict with asset hrefs (nir, swir16).
            bbox: (west, south, east, north) for windowed read.

        Returns:
            2D numpy array of NBR values, or None on failure.
        """
        assets = scene.get("assets", {})
        nir_href = assets.get(ASSET_NIR)
        swir_href = assets.get(ASSET_SWIR)

        if not nir_href or not swir_href:
            logger.warning("Scene %s missing NIR or SWIR assets", scene.get("id"))
            return None

        west, south, east, north = bbox

        try:
            nir = self._read_band_window(nir_href, west, south, east, north)
            swir = self._read_band_window(swir_href, west, south, east, north)

            if nir is None or swir is None:
                return None

            # Match shapes if slightly different (different band resolutions)
            min_h = min(nir.shape[0], swir.shape[0])
            min_w = min(nir.shape[1], swir.shape[1])
            nir = nir[:min_h, :min_w].astype(np.float32)
            swir = swir[:min_h, :min_w].astype(np.float32)

            # Compute NBR, avoiding division by zero
            denominator = nir + swir
            nbr = np.where(denominator > 0, (nir - swir) / denominator, np.nan)

            return nbr

        except Exception:
            logger.warning("Failed to read bands for scene %s", scene.get("id"), exc_info=True)
            return None

    def _read_band_window(
        self,
        href: str,
        west: float,
        south: float,
        east: float,
        north: float,
    ) -> np.ndarray | None:
        """Read a single band from a COG using a windowed read.

        IMPORTANT: Only reads the pixels within the bbox window.
        Never loads full scenes into memory.
        Reprojects WGS84 bbox to the COG's native CRS (typically UTM).

        Args:
            href: COG URL (https:// S3 signed URL).
            west, south, east, north: Bounding box in WGS84.

        Returns:
            2D numpy array, or None on failure.
        """
        from rasterio.warp import transform_bounds

        try:
            with rasterio.open(href) as src:
                # Reproject WGS84 bbox to the COG's native CRS
                native_bounds = transform_bounds(
                    "EPSG:4326", src.crs,
                    west, south, east, north,
                )
                window = from_bounds(*native_bounds, src.transform)

                # Clamp window to raster extent
                window = window.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
                if window.width < 1 or window.height < 1:
                    logger.warning("Window outside raster bounds for %s", href[:60])
                    return None

                data = src.read(1, window=window)
                if data.size == 0:
                    return None
                return data
        except Exception:
            logger.warning("COG read failed: %s", href[:80], exc_info=True)
            return None
