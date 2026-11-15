"""ACME.sh SSL Certificate Manager integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography import x509

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_AUTO_RENEW,
    CONF_DAYS,
    DEFAULT_DAYS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]

# The add-on installs certificates under /ssl, which the supervisor also mounts
# into the Home Assistant container. A Core/Container install may instead keep
# them below the configuration directory.
_CERT_FILE_NAMES = (
    "acme.sh/{domain}/fullchain.pem",
    "{domain}.pem",
    "{domain}-fullchain.pem",
    "{domain}/fullchain.pem",
)


def _ssl_dirs(hass: HomeAssistant) -> list[Path]:
    """Return the candidate SSL directories, most specific first."""
    dirs = [Path("/ssl"), Path(hass.config.path("ssl"))]
    return [d for i, d in enumerate(dirs) if d not in dirs[:i]]


def _find_cert_file(hass: HomeAssistant, domain: str) -> Path | None:
    """Locate the fullchain certificate file for a domain."""
    for base in _ssl_dirs(hass):
        for name in _CERT_FILE_NAMES:
            candidate = base / name.format(domain=domain)
            if candidate.is_file():
                return candidate
    return None


def _parse_cert(path: Path) -> dict[str, Any]:
    """Read expiry and issuer information from a PEM certificate."""
    cert = x509.load_pem_x509_certificate(path.read_bytes())
    expiry = cert.not_valid_after_utc
    return {
        "expiry_date": expiry.strftime("%Y-%m-%d %H:%M:%S"),
        "days_remaining": (expiry - datetime.now(UTC)).days,
        "issuer": cert.issuer.rfc4514_string(),
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ACME.sh from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    async def async_update_data() -> dict[str, Any]:
        """Read certificate information from the SSL directory."""
        domains = entry.data.get("domains") or []
        if isinstance(domains, str):
            domains = [d.strip() for d in domains.split(",") if d.strip()]

        main_domain = domains[0] if domains else ""
        cert_data: dict[str, Any] = {
            "domain": main_domain,
            "domains": domains,
            "status": "unknown",
            "expiry_date": None,
            "days_remaining": None,
            "issuer": None,
            "auto_renew": entry.options.get(CONF_AUTO_RENEW, True),
        }

        if not main_domain:
            cert_data["status"] = "not_configured"
            return cert_data

        cert_file = await hass.async_add_executor_job(_find_cert_file, hass, main_domain)
        if cert_file is None:
            _LOGGER.debug("No certificate found for %s", main_domain)
            cert_data["status"] = "not_found"
            return cert_data

        cert_data["certificate_path"] = str(cert_file)

        try:
            info = await hass.async_add_executor_job(_parse_cert, cert_file)
        except Exception:
            _LOGGER.exception("Error reading certificate %s", cert_file)
            cert_data["status"] = "error"
            return cert_data

        cert_data.update(info)

        days_remaining = cert_data["days_remaining"]
        threshold = entry.data.get(CONF_DAYS, DEFAULT_DAYS)
        if days_remaining < 0:
            cert_data["status"] = "expired"
        elif days_remaining < threshold:
            cert_data["status"] = "renewal_required"
        else:
            cert_data["status"] = "valid"

        return cert_data

    coordinator = DataUpdateCoordinator(
        hass,
        logger=_LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        update_method=async_update_data,
        update_interval=timedelta(hours=6),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "config": entry.data,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options for the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
