type GlobeDensityItem = {
  accent: string;
  label: string;
  value: number;
};

type GlobeDataDensityProps = {
  items: GlobeDensityItem[];
  title: string;
};

export function GlobeDataDensity({ items, title }: GlobeDataDensityProps) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  const maxValue = Math.max(...items.map((item) => item.value), 1);

  return (
    <div className="globe-density" aria-label={`${title}: ${total} visible items`}>
      <div className="globe-density__header">
        <p className="globe-panel__label">{title}</p>
        <span>{total}</span>
      </div>
      <div className="globe-density__stack" role="list">
        {items.map((item) => {
          const width = item.value > 0 ? Math.max(8, (item.value / maxValue) * 100) : 0;
          return (
            <div
              key={item.label}
              className="globe-density__row"
              role="listitem"
              aria-label={`${item.label} ${item.value}`}
            >
              <span className="globe-density__label">{item.label}</span>
              <span className="globe-density__track" aria-hidden="true">
                <span
                  className="globe-density__bar"
                  style={{
                    backgroundColor: item.accent,
                    color: item.accent,
                    width: `${width}%`,
                  }}
                />
              </span>
              <span className="globe-density__value">{item.value}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
