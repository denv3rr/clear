import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

type CapturedGlobeFixtureEnvelope = {
  fixture_id: string;
  fixture_version: number;
  captured_at_utc: string;
  scene_payload: Record<string, unknown>;
  intel_meta_payload: Record<string, unknown>;
  provenance: {
    news_cache?: {
      path?: string;
      item_count?: number;
      sources?: string[];
    };
  };
};

function loadFixture<T>(name: string) {
  const raw = fs.readFileSync(path.join(__dirname, `${name}.json`), "utf-8");
  return JSON.parse(raw) as T;
}

export function loadCapturedIntelGlobeFixture(): CapturedGlobeFixtureEnvelope {
  const fixture = loadFixture<CapturedGlobeFixtureEnvelope>("intel-globe.fixture");
  if (fixture.fixture_version !== 1) {
    throw new Error(`Unsupported globe fixture version: ${fixture.fixture_version}`);
  }
  if (!fixture.scene_payload || !fixture.intel_meta_payload) {
    throw new Error("Captured globe fixture is missing required payloads.");
  }
  return fixture;
}
