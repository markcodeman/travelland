import { useState } from 'react';

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

  return (
    <div className="space-y-2 text-white">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{icon}</span>
          <div className="text-lg font-semibold">
            {tempC === null ? '—' : unit === 'C' ? `${Math.round(tempC)}°C` : `${tempF}°F`}
            {city && <span className="text-white/80"> · {city}</span>}
          </div>
        </div>
        <div className="flex gap-1 text-xs font-semibold bg-white/10 rounded-full p-1">
          <button
            className={`px-2 py-1 rounded-full ${unit === 'C' ? 'bg-white text-slate-900' : 'text-white/80'}`}
            onClick={() => setUnit('C')}
          >
            °C
          </button>
          <button
            className={`px-2 py-1 rounded-full ${unit === 'F' ? 'bg-white text-slate-900' : 'text-white/80'}`}
            onClick={() => setUnit('F')}
          >
            °F
          </button>
        </div>
      </div>

      {summary && <div className="text-sm text-white/90">{summary}</div>}
      {current.apparent_temperature !== undefined && (
        <div className="text-xs text-white/80">Feels like {Math.round(current.apparent_temperature)}°</div>
      )}

      <div className="flex flex-wrap gap-2 text-xs">
        {sunrise && (
          <span className="px-2 py-1 rounded-full bg-white/15 border border-white/10">Sunrise {formatTimeOnly(sunrise)}</span>
        )}
        {sunset && (
          <span className="px-2 py-1 rounded-full bg-white/15 border border-white/10">Sunset {formatTimeOnly(sunset)}</span>
        )}
        {windKph !== null && (
          <span className="px-2 py-1 rounded-full bg-white/15 border border-white/10">
            Wind {unit === 'C' ? `${Math.round(windKph)} km/h` : `${windMph} mph`}
          </span>
        )}
      </div>
    </div>
  );
}
