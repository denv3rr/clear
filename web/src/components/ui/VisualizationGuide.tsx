type VisualizationGuideProps = {
  summary: string;
  details?: string[];
  label?: string;
};

export function VisualizationGuide({
  summary,
  details = [],
  label = "How to read this",
}: VisualizationGuideProps) {
  return (
    <div className="visualization-guide">
      <p>{summary}</p>
      {details.length ? (
        <details>
          <summary>{label}</summary>
          <ul>
            {details.map((detail) => (
              <li key={detail}>{detail}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
