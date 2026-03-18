export type LeafletLib = typeof import("leaflet");

let cached: LeafletLib | null = null;

export async function loadLeaflet(): Promise<LeafletLib> {
  if (cached) {
    return cached;
  }
  const mod = await import("leaflet");
  const leaflet = (mod as { default?: LeafletLib }).default ?? (mod as LeafletLib);
  cached = leaflet;
  return leaflet;
}
