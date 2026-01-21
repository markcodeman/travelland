import React, { useState } from 'react';

function weatherEmoji(code) {
  // simple mapping for common weathercodes used by Open-Meteo
  if (code === undefined || code === null) return '🌤️';
  const c = Number(code);
  if (c === 0) return '☀️';
  if (c === 1 || c === 2) return '🌤️';
  if (c === 3) return '☁️';
  if (c >= 45 && c <= 48) return '🌫️';
  if ((c >= 51 && c <= 67) || (c >= 80 && c <= 82)) return '🌧️';
  if ((c >= 71 && c <= 77) || (c >= 85 && c <= 86)) return '❄️';
  if (c >= 95) return '⛈️';
  return '🌤️';
}

export default function WeatherDisplay({ weather, city }) {
  if (!weather) return null;
  const [unit, setUnit] = useState('C'); // 'C' or 'F'
  // support either being passed a full payload (with hourly/daily) or single current object
  const current = weather.current_weather ? weather.current_weather : weather;

  const tempC = (() => {
    const t = current.temperature ?? current.temp ?? current.temp_c ?? current.temp_celsius ?? null;
    return t === null || t === undefined ? null : Number(t);
  })();
  const tempF = tempC !== null ? Math.round((tempC * 9) / 5 + 32) : null;

  const windKph = (() => {
    const w = current.windspeed ?? current.wind_speed ?? current.wind_kph ?? current.windspeed_10m ?? null;
    return w === null || w === undefined ? null : Number(w);
  })();
  const windMph = windKph !== null ? Math.round(windKph * 0.621371) : null;

  const code = current.weathercode ?? current.code ?? null;
  const icon = weather.icon ?? weatherEmoji(code);
  const summary = weather.summary ?? weather.weather ?? current.weather ?? null;

  function formatLocal(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleString();
    } catch (e) {
      return iso;
    }
  }

  function formatTimeOnly(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return iso;
    }
  }

  const sunrise = (weather.daily && weather.daily.sunrise && weather.daily.sunrise[0]) || null;
  const sunset = (weather.daily && weather.daily.sunset && weather.daily.sunset[0]) || null;

  const dayOfWeek = current.time ? new Date(current.time).toLocaleDateString([], { weekday: 'long' }) : null;

  return (
    <div className="weather-display hero-weather">
      <div className="weather-left">
        <div className="weather-icon">{icon}</div>
      </div>
      <div className="weather-main">
        <div className="weather-temp">
          {tempC === null ? (
            '—'
          ) : unit === 'C' ? (
            <>{Math.round(tempC)}°C</>
          ) : (
            <>{tempF}°F</>
          )}
          {city && <span className="weather-city"> in {city}</span>}
        </div>

        {dayOfWeek && <div className="weather-day">{dayOfWeek}</div>}

        <div className="weather-units">
          <button className={`unit-btn ${unit === 'C' ? 'active' : ''}`} onClick={() => setUnit('C')}>°C</button>
          <button className={`unit-btn ${unit === 'F' ? 'active' : ''}`} onClick={() => setUnit('F')}>°F</button>
        </div>

        {summary && <div className="weather-summary">{summary}</div>}
        {current.time && <div className="weather-localtime">Local time: {formatLocal(current.time)}</div>}
        {sunrise && <div className="weather-sun">Sunrise: {formatTimeOnly(sunrise)}</div>}
        {sunset && <div className="weather-sun">Sunset: {formatTimeOnly(sunset)}</div>}
        {windKph !== null && (
          <div className="weather-wind">Wind: {unit === 'C' ? `${Math.round(windKph)} km/h` : `${windMph} mph`}</div>
        )}
        {/* optional additions: feels_like, humidity, precipitation if available */}
        {current.apparent_temperature !== undefined && (
          <div className="weather-feels">Feels like: {Math.round(current.apparent_temperature)}°</div>
        )}
      </div>
    </div>
  );
}
