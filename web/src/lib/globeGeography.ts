type GlobeGeographySource = {
  name: string;
  dataset: string;
  source_page: string;
  land_url: string;
  coastline_url: string;
  coordinate_system: string;
  generated_utc: string;
  land_polygon_count: number;
  coastline_count: number;
};

export type GlobeGeographyData = {
  source: GlobeGeographySource;
  land_polygons: number[][][][];
  coast_lines: number[][][];
};

let geographyPromise: Promise<GlobeGeographyData> | null = null;
const geographyCanvasCache = new Map<number, HTMLCanvasElement>();

function projectToCanvas(
  lon: number,
  lat: number,
  width: number,
  height: number,
) {
  return {
    x: ((lon + 180) / 360) * width,
    y: ((90 - lat) / 180) * height,
  };
}

function drawPolygonPath(
  ctx: CanvasRenderingContext2D,
  rings: number[][][],
  width: number,
  height: number,
) {
  for (const ring of rings) {
    if (!ring.length) continue;
    ring.forEach((point, index) => {
      const { x, y } = projectToCanvas(Number(point[0]), Number(point[1]), width, height);
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.closePath();
  }
}

function drawLinePath(
  ctx: CanvasRenderingContext2D,
  line: number[][],
  width: number,
  height: number,
) {
  if (!line.length) return;
  line.forEach((point, index) => {
    const { x, y } = projectToCanvas(Number(point[0]), Number(point[1]), width, height);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
}

function drawGraticule(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
) {
  ctx.save();
  ctx.strokeStyle = "rgba(117, 215, 255, 0.08)";
  ctx.lineWidth = 1;
  for (let lon = -150; lon <= 180; lon += 30) {
    ctx.beginPath();
    for (let lat = -90; lat <= 90; lat += 2) {
      const { x, y } = projectToCanvas(lon, lat, width, height);
      if (lat === -90) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    ctx.beginPath();
    for (let lon = -180; lon <= 180; lon += 2) {
      const { x, y } = projectToCanvas(lon, lat, width, height);
      if (lon === -180) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
  }
  ctx.restore();
}

export function loadGlobeGeography() {
  if (!geographyPromise) {
    geographyPromise = fetch("/globe-data/natural-earth-110m.json")
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Globe geography unavailable (${response.status}).`);
        }
        return (await response.json()) as GlobeGeographyData;
      })
      .catch((error) => {
        geographyPromise = null;
        throw error;
      });
  }
  return geographyPromise;
}

export function buildGlobeContextCanvas(
  geography: GlobeGeographyData,
  size = 2048,
) {
  const cachedCanvas = geographyCanvasCache.get(size);
  if (cachedCanvas) {
    return cachedCanvas;
  }
  const canvas = document.createElement("canvas");
  canvas.width = size * 2;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("2D canvas unavailable for globe geography rendering.");
  }
  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);

  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, "rgba(16, 40, 51, 0.35)");
  gradient.addColorStop(0.5, "rgba(7, 17, 26, 0)");
  gradient.addColorStop(1, "rgba(9, 48, 40, 0.35)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  drawGraticule(ctx, width, height);

  ctx.save();
  ctx.beginPath();
  for (const polygon of geography.land_polygons) {
    drawPolygonPath(ctx, polygon, width, height);
  }
  ctx.fillStyle = "rgba(55, 172, 132, 0.14)";
  ctx.fill("evenodd");
  ctx.restore();

  ctx.save();
  ctx.strokeStyle = "rgba(72, 241, 166, 0.78)";
  ctx.lineWidth = 1.3;
  ctx.shadowColor = "rgba(72, 241, 166, 0.4)";
  ctx.shadowBlur = 4;
  for (const line of geography.coast_lines) {
    ctx.beginPath();
    drawLinePath(ctx, line, width, height);
    ctx.stroke();
  }
  ctx.restore();

  geographyCanvasCache.set(size, canvas);
  return canvas;
}
