"""Support for smartlife cameras."""
from __future__ import annotations

from tuya_sharing import Manager, CustomerDevice

from homeassistant.components import ffmpeg
from homeassistant.components.camera import Camera as CameraEntity, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantSmartLifeData
from .base import SmartLifeEntity
from .const import DOMAIN, SMART_LIFE_DISCOVERY_NEW, DPCode

# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
CAMERAS: tuple[str, ...] = (
    # Smart Camera (including doorbells)
    # https://developer.tuya.com/en/docs/iot/categorysgbj?id=Kaiuz37tlpbnu
    "sp",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up smartlife cameras dynamically through smartlife discovery."""
    hass_data: HomeAssistantSmartLifeData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered smartlife camera."""
        entities: list[SmartLifeCameraEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if device.category in CAMERAS:
                entities.append(SmartLifeCameraEntity(device, hass_data.manager))

        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, SMART_LIFE_DISCOVERY_NEW, async_discover_device)
    )


class SmartLifeCameraEntity(SmartLifeEntity, CameraEntity):
    """smartlife Camera Entity."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_brand = "smart life"

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
    ) -> None:
        """Init smartlife Camera."""
        super().__init__(device, device_manager)
        CameraEntity.__init__(self)
        self._attr_model = device.product_name

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self.device.status.get(DPCode.RECORD_SWITCH, False)

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return self.device.status.get(DPCode.MOTION_SWITCH, False)

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return await self.hass.async_add_executor_job(
            self.device_manager.get_device_stream_allocate,
            self.device.id,
            "rtsp",
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        stream_source = await self.stream_source()
        if not stream_source:
            return None
        return await ffmpeg.async_get_image(
            self.hass,
            stream_source,
            width=width,
            height=height,
        )

    def enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        self._send_command([{"code": DPCode.MOTION_SWITCH, "value": True}])

    def disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        self._send_command([{"code": DPCode.MOTION_SWITCH, "value": False}])