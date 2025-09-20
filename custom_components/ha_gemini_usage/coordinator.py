"""DataUpdateCoordinator for the Google Gemini Usage integration."""
import logging
from datetime import timedelta
from collections import defaultdict
import datetime

from homeassistant.util import dt as dt_util

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_period_start(period: str, now: datetime.datetime) -> datetime.datetime:
    """Get the start of the current period (daily, weekly, monthly)."""
    if period == "daily":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_of_day - datetime.timedelta(days=start_of_day.weekday())
    if period == "monthly":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return now


class GeminiUsageDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Gemini usage data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.api_key = entry.data[CONF_API_KEY]

        now = dt_util.utcnow()
        self.usage_data = {
            "total_requests": 0,
            "daily_requests": 0,
            "weekly_requests": 0,
            "monthly_requests": 0,
            "last_reset_daily": get_period_start("daily", now),
            "last_reset_weekly": get_period_start("weekly", now),
            "last_reset_monthly": get_period_start("monthly", now),
            "models": defaultdict(
                lambda: {
                    "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                    "daily_input_tokens": 0, "daily_output_tokens": 0, "daily_total_tokens": 0,
                    "weekly_input_tokens": 0, "weekly_output_tokens": 0, "weekly_total_tokens": 0,
                    "monthly_input_tokens": 0, "monthly_output_tokens": 0, "monthly_total_tokens": 0,
                }
            ),
        }

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )

    def _reset_if_needed(self):
        """Check if any of the periods need to be reset."""
        now = dt_util.utcnow()

        # Check daily reset
        if now >= self.usage_data["last_reset_daily"] + datetime.timedelta(days=1):
            self.usage_data["last_reset_daily"] = get_period_start("daily", now)
            self.usage_data["daily_requests"] = 0
            for model in self.usage_data["models"].values():
                model["daily_input_tokens"] = 0
                model["daily_output_tokens"] = 0
                model["daily_total_tokens"] = 0

        # Check weekly reset
        if now >= self.usage_data["last_reset_weekly"] + datetime.timedelta(weeks=1):
            self.usage_data["last_reset_weekly"] = get_period_start("weekly", now)
            self.usage_data["weekly_requests"] = 0
            for model in self.usage_data["models"].values():
                model["weekly_input_tokens"] = 0
                model["weekly_output_tokens"] = 0
                model["weekly_total_tokens"] = 0

        # Check monthly reset
        if now.month != self.usage_data["last_reset_monthly"].month:
            self.usage_data["last_reset_monthly"] = get_period_start("monthly", now)
            self.usage_data["monthly_requests"] = 0
            for model in self.usage_data["models"].values():
                model["monthly_input_tokens"] = 0
                model["monthly_output_tokens"] = 0
                model["monthly_total_tokens"] = 0


    async def _async_update_data(self):
        """Fetch data and reset periodic counters if necessary."""
        self._reset_if_needed()
        return self.usage_data

    def update_usage_stats(self, model_name: str, result):
        """Update usage stats after an API call."""
        if not hasattr(result, 'usage_metadata'):
            return

        # Check for resets before updating
        self._reset_if_needed()

        usage = result.usage_metadata
        input_tokens = getattr(usage, 'prompt_token_count', 0)
        output_tokens = getattr(usage, 'candidates_token_count', 0)
        total_tokens = getattr(usage, 'total_token_count', 0)

        # Update total requests
        self.usage_data["total_requests"] += 1
        self.usage_data["daily_requests"] += 1
        self.usage_data["weekly_requests"] += 1
        self.usage_data["monthly_requests"] += 1

        # Update model stats
        model_stats = self.usage_data["models"][model_name]
        model_stats["input_tokens"] += input_tokens
        model_stats["output_tokens"] += output_tokens
        model_stats["total_tokens"] += total_tokens
        
        # Update periodic model stats
        model_stats["daily_input_tokens"] += input_tokens
        model_stats["daily_output_tokens"] += output_tokens
        model_stats["daily_total_tokens"] += total_tokens
        
        model_stats["weekly_input_tokens"] += input_tokens
        model_stats["weekly_output_tokens"] += output_tokens
        model_stats["weekly_total_tokens"] += total_tokens

        model_stats["monthly_input_tokens"] += input_tokens
        model_stats["monthly_output_tokens"] += output_tokens
        model_stats["monthly_total_tokens"] += total_tokens

        # Schedule an immediate refresh to update sensors
        self.async_schedule_refresh()
