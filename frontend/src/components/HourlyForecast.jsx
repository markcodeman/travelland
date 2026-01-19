import React from 'react';

function fmtHour(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return iso;
  }
}

function isDayForTime(iso, daily) {
  if (!daily || !daily.time) return true;
  try {
    const dt = new Date(iso);
    const dateStr = dt.toISOString().slice(0, 10);
    const idx = daily.time.indexOf(dateStr);
    if (idx === -1) return true;
    const sunrise = new Date(daily.sunrise[idx]);
    const sunset = new Date(daily.sunset[idx]);
    return dt >= sunrise && dt < sunset;
  } catch (e) {
    return true;
  }
}

function makeSparkPoints(values, height = 36) {
  if (!values || values.length === 0) return '';
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = ((max - v) / range) * height;
    return `${x},${y}`;
  }).join(' ');
}

export default function HourlyForecast({ weather, unit = 'C' }) {
  if (!weather || !weather.hourly) return null;
  const hourly = weather.hourly;
  const times = hourly.time || [];
  const temps = hourly.temperature_2m || [];
  const precipProb = hourly.precipitation_probability || [];
  const precip = hourly.precipitation || [];
  const wind = hourly.windspeed_10m || [];

  // find 'now' index
  const now = new Date();
  let startIdx = 0;
  for (let i = 0; i < times.length; i++) {
    const t = new Date(times[i]);
    if (t >= now) { startIdx = i; break; }
  }

  const windowHours = 24; // lookahead
  const endIdx = Math.min(times.length, startIdx + windowHours);

  // compute best 2-hour window: minimize avg precipitation probability, tie-breaker warmer avg temp
  let best = null;
  for (let i = startIdx; i + 1 < endIdx; i++) {
    const p1 = precipProb[i] ?? 0;
    const p2 = precipProb[i + 1] ?? 0;
    const avgP = (p1 + p2) / 2;
    const t1 = temps[i] ?? null;
    const t2 = temps[i + 1] ?? null;
    const avgT = (Number(t1 || 0) + Number(t2 || 0)) / 2;
    const score = avgP - (avgT - 10) * 0.01; // prefer slightly warmer when precip ties
    if (best === null || score < best.score) {
      best = { idx: i, avgP, avgT, score };
    }
  }

  const hours = [];
  for (let i = startIdx; i < endIdx; i++) {
    hours.push({
      time: times[i],
      temp: temps[i],
      precipProb: precipProb[i],
      precip: precip[i],
      wind: wind[i],
      isDay: isDayForTime(times[i], weather.daily)
    });
  }

  const tempsSlice = hours.map(h => h.temp);
  const precipSlice = hours.map(h => h.precip || 0);
  const precipMax = Math.max(...precipSlice, 1);

  const tempPoints = makeSparkPoints(tempsSlice, 36);

  return (
    <div className="hourly-forecast">
      <h3>Hourly (next 24h)</h3>
      <div className="hourly-sparklines">
        <svg className="temp-spark" viewBox={`0 0 100 36`} preserveAspectRatio="none">
          <polyline fill="none" stroke="#ff8c00" strokeWidth="1.5" points={tempPoints} />
        </svg>
        <svg className="precip-spark" viewBox={`0 0 100 36`} preserveAspectRatio="none">
          {precipSlice.map((p, i) => {
            const x = (i / (precipSlice.length - 1)) * 100;
            const h = (p / precipMax) * 36;
            return <rect key={i} x={`${x}%`} y={36 - h} width={`${100 / precipSlice.length}%`} height={h} fill="#2b8cff" rx="1" />;
          })}
        </svg>
      </div>

      <div className="hourly-strip">
        {hours.map((h, i) => {
          const isBest = best && i === (best.idx - startIdx);
          const p = h.precipProb ?? 0;
          return (
            <div key={h.time} className={`hour-cell ${isBest ? 'best' : ''}`}>
              <div className="hour-time">{fmtHour(h.time)}</div>
              <div className="hour-icon">{h.isDay ? '☀️' : '🌙'}</div>
              <div className="hour-precip">{p}%</div>
              <div className="hour-temp">{unit === 'C' ? Math.round(h.temp) + '°C' : Math.round(h.temp * 9/5 + 32) + '°F'}</div>
            </div>
          );
        })}
      </div>
      {best && (
        <div className="best-window">
          Best 2‑hour window: {fmtHour(times[best.idx])} — {fmtHour(times[best.idx + 1])} — low rain chance ({Math.round(best.avgP)}%)
        </div>
      )}
    </div>
  );
}
