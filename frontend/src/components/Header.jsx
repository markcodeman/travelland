
export default function Header({ city, neighborhood }) {
  return (
    <header className="bg-transparent">
      <div className="max-w-6xl mx-auto px-4 pt-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <img src="/marcos.webp" alt="Marco" className="h-32 w-auto object-contain drop-shadow" />
        </div>

        <div className="flex items-center gap-3">
          {(city || neighborhood) && (
            <div className="hidden sm:flex flex-col text-right">
              <span className="text-xs uppercase tracking-wide text-slate-500">Exploring</span>
              <span className="text-sm font-semibold text-slate-800">{neighborhood ? `${neighborhood}, ${city}` : city}</span>
            </div>
          )}
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-800 shadow-sm hover:shadow-md transition"
            aria-label="Menu"
          >
            <span className="text-lg" role="img" aria-label="hamburger">🍔</span>
            <span className="hidden sm:inline">Menu</span>
          </button>
        </div>
      </div>
    </header>
  );
}
