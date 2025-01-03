"""
Adds support for the Ariston Boiler
"""
import logging
from datetime import timedelta
from .const import param_zoned

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_COOL ,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    HVAC_MODE_COOL,
    ClimateEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    UnitOfTemperature,
)

from .const import (
    CONF_CLIMATES,
    DATA_ARISTON,
    DEVICES,
    OPTIONS_TXT,
    PARAM_CH_MODE,
    PARAM_MODE,
    PARAM_CH_SET_TEMPERATURE,
    PARAM_CH_DETECTED_TEMPERATURE,
    PARAM_CH_FLAME,
    PARAM_HOLIDAY_MODE,
    VAL_WINTER,
    VAL_SUMMER,
    VAL_HEATING_ONLY,
    VAL_COOLING,
    VAL_ON,
    VAL_MANUAL,
    VAL_PROGRAM,
    VAL_HOLIDAY,
    VAL_OFFLINE,
    VALUE,
    UNITS,
    MIN,
    MAX,
    STEP,
)

SCAN_INTERVAL = timedelta(seconds=2)
SUPPORT_FLAGS = ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE
UNKNOWN_TEMP = 0.0

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the Ariston Platform."""
    if discovery_info is None:
        return
    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_ARISTON][DEVICES][name]
    add_entities(
        [
            AristonThermostat(name, device, climate_name)
            for climate_name in discovery_info[CONF_CLIMATES]
        ],
        True,
    )

class AristonThermostat(ClimateEntity):
    """Representation of a Ariston Thermostat."""

    def __init__(self, name, device, climate_name):
        """Initialize the thermostat."""
        self._name = name
        self._api = device.api.ariston_api
        self._device = device.device
        self._climate_name = climate_name
        self._zone = int(climate_name[-1])

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"{self._climate_name}_climate"

    @property
    def icon(self):
        """Return the name of the Climate device."""
        try:
            if self._api.ch_available:
                current_mode = self._api.sensor_values[PARAM_MODE][VALUE]
            else:
                current_mode = VAL_OFFLINE
        except KeyError:
            return "mdi:radiator-off"
        if current_mode and current_mode in [VAL_WINTER, VAL_HEATING_ONLY]:
            return "mdi:radiator"
        else:
            return "mdi:radiator-off"

    @property
    def name(self):
        """Return the name of the Climate device."""
        return self._climate_name

    @property
    def should_poll(self):
        """Polling is required."""
        return True

    @property
    def min_temp(self):
        """Return minimum temperature."""
        try:
            minimum_temp = self._api.sensor_values[param_zoned(PARAM_CH_SET_TEMPERATURE, self._zone)][MIN]
        except KeyError:
            return UNKNOWN_TEMP
        return minimum_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        try:
            maximum_temp = self._api.sensor_values[param_zoned(PARAM_CH_SET_TEMPERATURE, self._zone)][MAX]
        except KeyError:
            return UNKNOWN_TEMP
        return maximum_temp

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        try:
            units = self._api.sensor_values[param_zoned(PARAM_CH_SET_TEMPERATURE, self._zone)][UNITS]
        except KeyError:
            return UnitOfTemperature.CELSIUS
        return units

    @property
    def current_temperature(self):
        """Return the current temperature."""
        try:
            current_temp = self._api.sensor_values[param_zoned(PARAM_CH_DETECTED_TEMPERATURE, self._zone)][VALUE]
        except KeyError:
            return UNKNOWN_TEMP
        return current_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        try:
            target_temp = self._api.sensor_values[param_zoned(PARAM_CH_SET_TEMPERATURE, self._zone)][VALUE]
        except KeyError:
            return UNKNOWN_TEMP
        return target_temp

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        try:
            climate_mode = self._api.sensor_values[PARAM_MODE][VALUE] 
            climate_ch_mode = self._api.sensor_values[param_zoned(PARAM_CH_MODE, self._zone)][VALUE] 
            curr_hvac_mode = HVAC_MODE_OFF
            if climate_mode and climate_mode in [VAL_WINTER, VAL_HEATING_ONLY]:
                if climate_ch_mode == VAL_MANUAL:
                    curr_hvac_mode = HVAC_MODE_HEAT
                elif climate_ch_mode == VAL_PROGRAM:
                    curr_hvac_mode = HVAC_MODE_AUTO
            if climate_mode and climate_mode in [VAL_COOLING]:
                if climate_ch_mode == VAL_MANUAL:
                    curr_hvac_mode = HVAC_MODE_COOL
                elif climate_ch_mode == VAL_PROGRAM:
                    curr_hvac_mode = HVAC_MODE_AUTO
        except KeyError:
            return HVAC_MODE_OFF
        return curr_hvac_mode

    @property
    def hvac_modes(self):
        """HVAC modes."""
        try:
            supported_ch_modes = self._api.sensor_values[param_zoned(PARAM_CH_MODE, self._zone)][OPTIONS_TXT] 
            supported_modes = []
            if supported_ch_modes and VAL_MANUAL in supported_ch_modes:
                supported_modes.append(HVAC_MODE_HEAT)
                if self._api._features.get("hasTwoCoolingTemp", False) or self._api._features.get("distinctHeatCoolSetpoints", False):
                    supported_modes.append(HVAC_MODE_COOL)
            if supported_ch_modes and VAL_PROGRAM in supported_ch_modes:
                supported_modes.append(HVAC_MODE_AUTO)
        except KeyError:
            return []
        return supported_modes

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        try:
            curr_hvac_action = CURRENT_HVAC_OFF
            climate_mode = self._api.sensor_values[PARAM_MODE][VALUE]
            if climate_mode in [VAL_WINTER, VAL_HEATING_ONLY]:
                ch_flame = self._api.sensor_values[param_zoned(PARAM_CH_FLAME, self._zone)][VALUE]
                if ch_flame == VAL_ON:
                    curr_hvac_action = CURRENT_HVAC_HEAT
                else:
                    curr_hvac_action = CURRENT_HVAC_IDLE
            if climate_mode in [VAL_COOLING]:
                ch_flame = self._api.sensor_values[param_zoned(PARAM_CH_FLAME, self._zone)][VALUE]
                if ch_flame == VAL_ON:
                    curr_hvac_action = CURRENT_HVAC_COOL
                else:
                    curr_hvac_action = CURRENT_HVAC_IDLE
        except KeyError:
            return CURRENT_HVAC_OFF
        return curr_hvac_action

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        try:
            curr_preset_mode = self._api.sensor_values[PARAM_MODE][VALUE]
            if self._api.sensor_values[PARAM_HOLIDAY_MODE][VALUE] == VAL_ON:
                curr_preset_mode = VAL_HOLIDAY
        except KeyError:
            return VAL_OFFLINE
        return curr_preset_mode

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        try:
            all_presets = self._api.sensor_values[PARAM_MODE][OPTIONS_TXT]
        except KeyError:
            return []
        return all_presets

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def available(self):
        """Return True if entity is available."""
        return self._api.ch_available

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        try:
            step = self._api.sensor_values[param_zoned(PARAM_CH_SET_TEMPERATURE, self._zone)][STEP]
        except KeyError:
            return 0.5
        return step

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        supported_modes = self._api.sensor_values[PARAM_MODE][OPTIONS_TXT]
        current_mode = self._api.sensor_values[PARAM_MODE][VALUE]
        if hvac_mode == HVAC_MODE_OFF:
            self._api.set_http_data(**{PARAM_MODE: VAL_SUMMER})
        elif hvac_mode == HVAC_MODE_AUTO:
            ch_mode = VAL_PROGRAM
            if current_mode in [VAL_WINTER, VAL_HEATING_ONLY, VAL_COOLING]:
                # if already heating or cooling just change CH mode
                self._api.set_http_data(**{param_zoned(PARAM_CH_MODE, self._zone): ch_mode})
            elif current_mode == VAL_SUMMER:
                # DHW is working, so use Winter where CH and DHW are active
                self._api.set_http_data(
                    **{PARAM_MODE: VAL_WINTER, param_zoned(PARAM_CH_MODE, self._zone): ch_mode}
                )
            else:
                # hvac is OFF, so use Heating only, if not supported then winter
                if VAL_HEATING_ONLY in supported_modes:
                    self._api.set_http_data(
                        **{PARAM_MODE: VAL_HEATING_ONLY, param_zoned(PARAM_CH_MODE, self._zone): ch_mode}
                    )
                else:
                    self._api.set_http_data(
                        **{PARAM_MODE: VAL_WINTER, param_zoned(PARAM_CH_MODE, self._zone): ch_mode}
                    )
        elif hvac_mode == HVAC_MODE_HEAT:
            ch_mode = VAL_MANUAL            
            if current_mode in [VAL_WINTER, VAL_HEATING_ONLY]:
                # if already heating, change CH mode
                self._api.set_http_data(**{param_zoned(PARAM_CH_MODE, self._zone): ch_mode})
            elif current_mode in [VAL_SUMMER, VAL_COOLING]:
                # DHW is working, so use Winter and change mode
                self._api.set_http_data(
                    **{PARAM_MODE: VAL_WINTER, param_zoned(PARAM_CH_MODE, self._zone): ch_mode}
                )
            else:
                # hvac is OFF, so use Heating only, if not supported then winter
                if VAL_HEATING_ONLY in supported_modes:
                    self._api.set_http_data(
                        **{PARAM_MODE: VAL_HEATING_ONLY, param_zoned(PARAM_CH_MODE, self._zone): ch_mode}
                    )
                else:
                    self._api.set_http_data(
                        **{PARAM_MODE: VAL_WINTER, param_zoned(PARAM_CH_MODE, self._zone): ch_mode}
                    )
        elif hvac_mode == HVAC_MODE_COOL:
            ch_mode = VAL_MANUAL
            self._api.set_http_data(**{PARAM_MODE: VAL_COOLING, param_zoned(PARAM_CH_MODE, self._zone): ch_mode})

    def set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        self._api.set_http_data(**{PARAM_MODE: preset_mode})

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        new_temperature = kwargs.get(ATTR_TEMPERATURE)
        if new_temperature is not None:
            self._api.set_http_data(**{param_zoned(PARAM_CH_SET_TEMPERATURE, self._zone): new_temperature})

    def update(self):
        """Update all Node data from Hive."""
        return
