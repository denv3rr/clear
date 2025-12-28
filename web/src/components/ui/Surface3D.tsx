import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";

const Plot = createPlotlyComponent(Plotly);

type Surface3DProps = {
  title: string;
  z: number[][];
  x?: number[];
  y?: number[];
  height?: number;
  className?: string;
};

export function Surface3D({
  title,
  z,
  x,
  y,
  height = 320,
  className = ""
}: Surface3DProps) {
  const hasData = Array.isArray(z) && z.length > 0 && Array.isArray(z[0]) && z[0].length > 0;
  const data = hasData
    ? [
        {
          type: "surface",
          z,
          x,
          y,
          colorscale: [
            [0, "rgba(5,6,8,0.6)"],
            [0.25, "rgba(26,64,52,0.7)"],
            [0.55, "rgba(72,241,166,0.65)"],
            [1, "rgba(72,241,166,0.95)"]
          ],
          showscale: false,
          opacity: 0.92,
          lighting: {
            ambient: 0.45,
            diffuse: 0.85,
            specular: 0.45,
            roughness: 0.35,
            fresnel: 0.3
          },
          lightposition: { x: 120, y: 80, z: 180 }
        }
      ]
    : [];

  return (
    <div className={`glass-panel rounded-2xl p-4 surface-3d ${className}`}>
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-400">{title}</p>
        <p className="text-[11px] text-emerald-300">{hasData ? "3D Surface" : "No data"}</p>
      </div>
      <div className="mt-3">
        {hasData ? (
          <Plot
            data={data as any}
            layout={{
              autosize: true,
              height,
              margin: { l: 0, r: 0, t: 0, b: 0 },
              paper_bgcolor: "rgba(0,0,0,0)",
              plot_bgcolor: "rgba(0,0,0,0)",
              scene: {
                bgcolor: "rgba(0,0,0,0)",
                xaxis: {
                  showgrid: true,
                  gridcolor: "rgba(72,241,166,0.08)",
                  zerolinecolor: "rgba(72,241,166,0.2)",
                  color: "#94a3b8"
                },
                yaxis: {
                  showgrid: true,
                  gridcolor: "rgba(72,241,166,0.08)",
                  zerolinecolor: "rgba(72,241,166,0.2)",
                  color: "#94a3b8"
                },
                zaxis: {
                  showgrid: true,
                  gridcolor: "rgba(72,241,166,0.08)",
                  zerolinecolor: "rgba(72,241,166,0.2)",
                  color: "#94a3b8"
                },
                camera: {
                  eye: { x: 1.15, y: 1.15, z: 0.9 },
                  center: { x: 0, y: 0, z: 0 }
                },
                aspectratio: { x: 1, y: 1, z: 0.6 }
              },
              dragmode: "orbit"
            }}
            config={{ displayModeBar: false, responsive: true, scrollZoom: true }}
            style={{ width: "100%", height: "100%" }}
            useResizeHandler
          />
        ) : (
          <div className="surface-empty">Surface data unavailable.</div>
        )}
      </div>
    </div>
  );
}
