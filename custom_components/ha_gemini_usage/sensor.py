"""Sensor platform for Google Gemini Usage."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SENSOR_CALLS_NAME
from .coordinator import GeminiUsageDataUpdateCoordinator

# Dictionary to map period names to data keys
PERIODS = {
    "Daily": "daily",
    "Weekly": "weekly",
    "Monthly": "monthly",
}

TOKEN_TYPES = {
    "Total": "total",
    "Input": "input",
    "Output": "output",
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: GeminiUsageDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_config_entry_first_refresh()

    entities = []

    # --- Total Increasing Sensors (survive restarts) ---
    entities.append(TotalCallsSensor(coordinator, entry))

    # --- Periodic Usage Sensors (reset on restart) ---
    for period_name, period_key in PERIODS.items():
        entities.append(PeriodicCallsSensor(coordinator, entry, period_name, period_key))
    
    # --- Model-Specific Sensors ---
    if "models" in coordinator.data:
        for model_name in coordinator.data["models"]:
            # Total increasing token sensors
            entities.append(ModelTokenSensor(coordinator, entry, model_name, "Total", "total"))
            entities.append(ModelTokenSensor(coordinator, entry, model_name, "Input", "input"))
            entities.append(ModelTokenSensor(coordinator, entry, model_name, "Output", "output"))

            # Periodic token sensors
            for period_name, period_key in PERIODS.items():
                for token_type_name, token_type_key in TOKEN_TYPES.items():
                    entities.append(
                        PeriodicModelTokenSensor(
                            coordinator, entry, model_name, 
                            period_name, period_key, 
                            token_type_name, token_type_key
                        )
                    )

    async_add_entities(entities)


class BaseGeminiSensor(CoordinatorEntity[GeminiUsageDataUpdateCoordinator], SensorEntity):
    """Base class for Gemini sensors."""
    def __init__(self, coordinator: GeminiUsageDataUpdateCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Google Gemini API Usage",
            "manufacturer": "Google",
        }

# --- SENSORS FOR TOTAL INCREASING VALUES ---

class TotalCallsSensor(BaseGeminiSensor):
    """Representation of a total API calls sensor."""
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:server-network"
    _attr_native_unit_of_measurement = "calls"

    def __init__(self, coordinator: GeminiUsageDataUpdateCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_name = SENSOR_CALLS_NAME
        self._attr_unique_id = f"{entry.entry_id}_total_calls"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("total_requests") if self.coordinator.data else None


class ModelTokenSensor(BaseGeminiSensor):
    """Sensor for a specific token type (total, input, output) for a model."""
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:chip"
    _attr_native_unit_of_measurement = "tokens"

    def __init__(self, coordinator, entry, model_name, token_type_name, token_type_key):
        super().__init__(coordinator, entry)
        self._model_name = model_name
        self._token_type_key = token_type_key
        self._attr_name = f"{model_name.replace('-', ' ').title()} {token_type_name} Tokens"
        self._attr_unique_id = f"{entry.entry_id}_{model_name}_{token_type_key}_tokens"
    
    @property
    def native_value(self) -> int | None:
        if self.coordinator.data:
            return self.coordinator.data["models"][self._model_name].get(f"{self._token_type_key}_tokens")
        return None

    @property
    def extra_state_attributes(self):
        return {"model": self._model_name}

# --- SENSORS FOR PERIODIC (RESETTING) VALUES ---

class PeriodicCallsSensor(BaseGeminiSensor):
    """Representation of a periodic API calls sensor (daily, weekly, monthly)."""
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:server-network"
    _attr_native_unit_of_measurement = "calls"

    def __init__(self, coordinator, entry, period_name, period_key):
        super().__init__(coordinator, entry)
        self._period_key = period_key
        self._attr_name = f"{SENSOR_CALLS_NAME} {period_name}"
        self._attr_unique_id = f"{entry.entry_id}_{period_key}_calls"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get(f"{self._period_key}_requests") if self.coordinator.data else None

    @property
    def last_reset(self):
        return self.coordinator.data.get(f"last_reset_{self._period_key}") if self.coordinator.data else None


class PeriodicModelTokenSensor(BaseGeminiSensor):
    """Sensor for periodic token usage for a model."""
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:chip"
    _attr_native_unit_of_measurement = "tokens"

    def __init__(self, coordinator, entry, model_name, period_name, period_key, token_type_name, token_type_key):
        super().__init__(coordinator, entry)
        self._model_name = model_name
        self._period_key = period_key
        self._token_type_key = token_type_key
        self._attr_name = f"{model_name.replace('-', ' ').title()} {token_type_name} Tokens {period_name}"
        self._attr_unique_id = f"{entry.entry_id}_{model_name}_{period_key}_{token_type_key}_tokens"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data:
            key = f"{self._period_key}_{self._token_type_key}_tokens"
            return self.coordinator.data["models"][self._model_name].get(key)
        return None

    @property
    def last_reset(self):
        return self.coordinator.data.get(f"last_reset_{self._period_key}") if self.coordinator.data else None
    
    @property
    def extra_state_attributes(self):
        return {"model": self._model_name}
