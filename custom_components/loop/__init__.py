"""The Loop Energy Sensor integration."""
from __future__ import annotations

import asyncio
import logging
import requests
import time
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.core import callback
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, HTTP_OK
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import (
    DOMAIN,
    LIVE_ENDPOINT,
    SCAN_INTERVAL,
    SIGNAL_NAME_PREFIX,
    MANUFACTURER,
    COGNITO_ENDPOINT,
    PHANTOM_ENDPOINT,
    CLIENT_ID,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Loop Energy Sensor from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    unique_id = entry.unique_id

    api = LoopEnergyApi(hass, unique_id, entry.data)
    domain_data[unique_id] = api
    await api.async_update()
    api.start_periodic_update()

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unique_id = entry.unique_id
    api = hass.data[DOMAIN][unique_id]

    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        api.stop_periodic_update()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class LoopEntity(SensorEntity):
    """Representation of a Loop base entity."""

    def __init__(
        self,
        api: LoopEnergyApi,
        type_name: str,
        icon: str,
        device_class: str,
        unit: str = None,
    ) -> None:
        """Initialize base entity."""
        self._api = api
        self._name = f"{api.name} {type_name}"
        self._icon = icon
        self._unique_id = f"{self._api.unique_id}-{type_name}"
        self._device_info = {
            "identifiers": {(DOMAIN, self._api.unique_id)},
            "name": self._api.name,
            "manufacturer": MANUFACTURER,
            "model": f"Loop Energy Sensor",
        }
        self._device_class = device_class
        self._extra_state_attributes = None
        self._disconnect_dispatcher = None
        self._state = None
        self._unit = unit

    @property
    def name(self) -> str:
        """Return name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self._device_info

    @property
    def device_class(self) -> str:
        """Return device class."""
        return self._device_class

    @property
    def icon(self) -> str:
        """Return icon."""
        return self._icon

    @property
    def should_poll(self) -> bool:
        """Disable polling."""
        return False

    async def async_update(self) -> None:
        """Fetch data from the server."""
        raise NotImplementedError()

    async def async_added_to_hass(self) -> None:
        """Connect dispatcher to signal from server."""
        self._disconnect_dispatcher = async_dispatcher_connect(
            self.hass, self._api.signal_name, self._update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher before removal."""
        self._disconnect_dispatcher()

    @callback
    def _update_callback(self) -> None:
        """Triggers update of properties after receiving signal from server."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return True

    @property
    def state(self) -> Any:
        """Return sensor state."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return sensor measurement unit."""
        return self._unit


class LoopEnergyApi:
    def __init__(
        self, hass: HomeAssistantType, unique_id: str, config_data: ConfigType
    ) -> None:
        """Initialize server instance."""
        self._hass = hass

        # Server data
        self._last_status_request_failed = False
        self.unique_id = unique_id
        self.name = "Loop"
        self.username = config_data[CONF_USERNAME]
        self.password = config_data[CONF_PASSWORD]
        self.access_token = None
        self.refresh_token = None
        self.id_token = None
        self.expires_at = 0
        self.last_request = 0

        self.session = requests.Session()

        self.phantom_load = None
        self.power_usage = None

        # Dispatcher signal name
        self.signal_name = f"{SIGNAL_NAME_PREFIX}_{self.unique_id}"

    def start_periodic_update(self) -> None:
        """Start periodic execution of update method."""
        self._stop_periodic_update = async_track_time_interval(
            self._hass, self.async_update, timedelta(seconds=SCAN_INTERVAL)
        )

    def stop_periodic_update(self) -> None:
        """Stop periodic execution of update method."""
        self._stop_periodic_update()

    async def async_update(self, now: datetime = None) -> None:
        await self.async_check_connection()
        await self._async_status_request()

        # Notify sensors about new data.
        async_dispatcher_send(self._hass, self.signal_name)

    def _password_auth(self) -> requests.Response:
        return self.session.post(
            COGNITO_ENDPOINT,
            json={
                "AuthFlow": "USER_PASSWORD_AUTH",
                "ClientId": CLIENT_ID,
                "AuthParameters": {
                    "USERNAME": self.username,
                    "PASSWORD": self.password,
                },
                "ClientMetadata": {},
            },
            headers={
                "User-Agent": "okhttp/3.12.1",
                "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth",
                "x-amz-user-agent": "aws-amplify/0.1.x react-native",
                "Content-Type": "application/x-amz-json-1.1",
            },
        )

    def _refresh_auth(self) -> requests.Response:
        return self.session.post(
            COGNITO_ENDPOINT,
            json={
                "ClientId": CLIENT_ID,
                "AuthFlow": "REFRESH_TOKEN_AUTH",
                "AuthParameters": {"REFRESH_TOKEN": self.refresh_token},
            },
            headers={
                "User-Agent": "okhttp/3.12.1",
                "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth",
                "x-amz-user-agent": "aws-amplify/0.1.x react-native",
                "Content-Type": "application/x-amz-json-1.1",
            },
        )

    def _live_data(self) -> requests.Response:
        auth = "Bearer " + self.id_token
        return self.session.get(
            LIVE_ENDPOINT,
            headers={
                "User-Agent": "okhttp/3.12.1",
                "content-type": "application/json",
                "accept": "application/json",
                "authorization": auth,
                "If-Modified-Since": time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time())
                ),
            },
        )

    def _phantom_load(self) -> requests.Response:
        auth = "Bearer " + self.id_token
        return self.session.get(
            PHANTOM_ENDPOINT,
            headers={
                "User-Agent": "okhttp/3.12.1",
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": auth,
                "If-Modified-Since": time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time())
                ),
            },
        )

    async def async_check_connection(self) -> bool:
        now = time.time()
        if self.expires_at > now and self.refresh_token is not None:
            return True
        elif self.expires_at < now and self.refresh_token is not None:
            await self._async_refresh_token()
            return True
        else:
            response = await self._hass.async_add_executor_job(self._password_auth)
            if response.status_code != HTTP_OK:
                return False
            self.access_token = (
                response.json().get("AuthenticationResult").get("AccessToken")
            )
            self.id_token = response.json().get("AuthenticationResult").get("IdToken")
            self.refresh_token = (
                response.json().get("AuthenticationResult").get("RefreshToken")
            )
            self.expires_at = (
                time.time()
                + response.json().get("AuthenticationResult").get("ExpiresIn")
                - 120
            )
            return True

    async def _async_refresh_token(self) -> bool:
        response = await self._hass.async_add_executor_job(self._refresh_auth)
        if response.status_code != HTTP_OK:
            return False
        self.access_token = (
            response.json().get("AuthenticationResult").get("AccessToken")
        )
        self.id_token = response.json().get("AuthenticationResult").get("IdToken")
        self.expires_at = (
            time.time()
            + response.json().get("AuthenticationResult").get("ExpiresIn")
            - 120
        )

    async def _async_status_request(self) -> None:
        """Request server status and update properties."""
        try:
            # status_response = await self._hass.async_add_executor_job(
            #    self._mc_status.status, self._MAX_RETRIES_STATUS
            # )
            if self.access_token:
                if (time.time() - self.last_request) > 1800:
                    phantom = await self._hass.async_add_executor_job(
                        self._phantom_load
                    )
                    if phantom.status_code == HTTP_OK:
                        self.phantom_load = round(phantom.json().get("power") / 1000, 3)
                    else:
                        _LOGGER.warning(phantom.content)

                # Got answer to request, update properties.
                live = await self._hass.async_add_executor_job(self._live_data)

                if live.status_code == HTTP_OK:
                    self.power_usage = round(abs(live.json().get("power")) / 1000, 3)
                else:
                    _LOGGER.warning(live.content)

                self.last_request = time.time()
                self._last_status_request_failed = False
        except OSError as error:
            # No answer to request, set all properties to unknown.
            self.power_usage = None
            self.phantom_load = None

            # Inform user once about failed update if necessary.
            if not self._last_status_request_failed:
                _LOGGER.warning(
                    "Updating the properties of '%s' failed - OSError: %s",
                    self.unique_id,
                    error,
                )
            self._last_status_request_failed = True
