import urllib.request
import urllib.parse
import json
from typing import Dict, Any

class OpenMeteoTool:
    """Free Open-Meteo Weather API integration (no API key required)."""

    WMO_WEATHER_CODES = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }

    @classmethod
    def get_weather(cls, location_name: str) -> Dict[str, Any]:
        """Fetch current weather and 3-day forecast for any city or region."""
        try:
            # Step 1: Geocode location to lat/lon
            encoded_loc = urllib.parse.quote(location_name)
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_loc}&count=1&language=en&format=json"
            
            with urllib.request.urlopen(geo_url, timeout=6) as response:
                geo_data = json.loads(response.read().decode("utf-8"))
            
            results = geo_data.get("results")
            if not results:
                return {"success": False, "error": f"Location '{location_name}' could not be resolved."}
            
            loc_info = results[0]
            lat = loc_info.get("latitude")
            lon = loc_info.get("longitude")
            resolved_name = f"{loc_info.get('name')}, {loc_info.get('country', '')}"
            timezone = loc_info.get("timezone", "auto")

            # Step 2: Fetch current weather & daily forecast
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&timezone={timezone}"
                f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m"
                f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
                f"&forecast_days=3"
            )
            
            with urllib.request.urlopen(weather_url, timeout=6) as response:
                w_data = json.loads(response.read().decode("utf-8"))
            
            current = w_data.get("current", {})
            daily = w_data.get("daily", {})
            units = w_data.get("current_units", {})

            current_code = current.get("weather_code", 0)
            condition_text = cls.WMO_WEATHER_CODES.get(current_code, "Fair")

            # Format 3-day forecast
            forecast_list = []
            dates = daily.get("time", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            codes = daily.get("weather_code", [])
            precips = daily.get("precipitation_probability_max", [])

            for i in range(len(dates)):
                day_code = codes[i] if i < len(codes) else 0
                forecast_list.append({
                    "date": dates[i],
                    "condition": cls.WMO_WEATHER_CODES.get(day_code, "Fair"),
                    "max_temp": f"{max_temps[i]}°C" if i < len(max_temps) else "N/A",
                    "min_temp": f"{min_temps[i]}°C" if i < len(min_temps) else "N/A",
                    "precip_prob": f"{precips[i]}%" if i < len(precips) else "0%"
                })

            return {
                "success": True,
                "location": resolved_name,
                "coordinates": {"latitude": lat, "longitude": lon},
                "temperature": f"{current.get('temperature_2m')} {units.get('temperature_2m', '°C')}",
                "feels_like": f"{current.get('apparent_temperature')} {units.get('apparent_temperature', '°C')}",
                "humidity": f"{current.get('relative_humidity_2m')} {units.get('relative_humidity_2m', '%')}",
                "wind_speed": f"{current.get('wind_speed_10m')} {units.get('wind_speed_10m', 'km/h')}",
                "condition": condition_text,
                "forecast": forecast_list,
                "source": "Open-Meteo"
            }
        except Exception as e:
            return {"success": False, "error": f"Open-Meteo error: {str(e)}"}
