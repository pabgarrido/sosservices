"""Data source adapters package."""

from app.services.base_adapter import BaseAdapter
from app.services.weather_adapter import IPMAWeatherAdapter
from app.services.fire_adapter import NASAFIRMSAdapter
from app.services.prociv_adapter import ProCivAdapter
from app.services.openweather_adapter import OpenWeatherAdapter

__all__ = [
    "BaseAdapter",
    "IPMAWeatherAdapter",
    "NASAFIRMSAdapter",
    "ProCivAdapter",
    "OpenWeatherAdapter",
]
