"use client";
import React, { useEffect, useRef, useState, useCallback } from "react";
import { api } from "@/lib/api";
import 'maplibre-gl/dist/maplibre-gl.css';

const CATEGORIES = ["All", "Drainage", "Roads", "Streetlights", "Garbage", "Trees", "Water"];
const DENSITY_COLORS = ["#EFF6FF", "#BFDBFE", "#93C5FD", "#3B82F6", "#1E3A8A"];

export default function PublicMapPage() {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapObj = useRef<any>(null);
  const [category, setCategory] = useState<string | undefined>();
  const [mapLoaded, setMapLoaded] = useState(false);
  const [wardError, setWardError] = useState(false);

  // Initialise MapLibre once
  useEffect(() => {
    if (!mapRef.current) return;
    import('maplibre-gl').then(mod => {
      const maplibregl = mod.default;
      mapObj.current = new maplibregl.Map({
        container: mapRef.current!,
        style: "https://tiles.openfreemap.org/styles/liberty",
        center: [77.2090, 28.6139],
        zoom: 10,
      });
      mapObj.current.on('load', () => setMapLoaded(true));
    });
    return () => mapObj.current?.remove();
  }, []);

  // Load ward density data and render heatmap
  const loadWardData = useCallback(async () => {
    if (!mapObj.current) return;
    setWardError(false);

    try {
      const [wardsRaw, densityData] = await Promise.all([
        api.wards.all(),
        api.analytics.wardDensity(category),
      ]);

      // Build lookup: ward_id → complaint count
      const densityMap: Record<string, number> = {};
      let maxCount = 1;
      for (const row of (densityData as any[])) {
        densityMap[row.ward_id] = row.count;
        if (row.count > maxCount) maxCount = row.count;
      }

      // GeoJSON FeatureCollection — augment each feature with complaint_count
      const geojson = typeof wardsRaw === "string" ? JSON.parse(wardsRaw) : wardsRaw;
      if (!geojson?.features) {
        setWardError(true);
        return;
      }

      const augmented = {
        ...geojson,
        features: geojson.features.map((f: any) => {
          const id = f.properties?.id ?? f.id;
          const count = densityMap[id] || 0;
          return { ...f, properties: { ...f.properties, complaint_count: count, density_pct: (count / maxCount) * 100 } };
        }),
      };

      // Remove stale layers and source before re-adding
      if (mapObj.current.getLayer("ward-fill"))    mapObj.current.removeLayer("ward-fill");
      if (mapObj.current.getLayer("ward-outline")) mapObj.current.removeLayer("ward-outline");
      if (mapObj.current.getSource("wards"))       mapObj.current.removeSource("wards");

      mapObj.current.addSource("wards", { type: "geojson", data: augmented });

      mapObj.current.addLayer({
        id: "ward-fill",
        type: "fill",
        source: "wards",
        paint: {
          "fill-color": [
            "interpolate", ["linear"], ["get", "density_pct"],
            0,   DENSITY_COLORS[0],
            25,  DENSITY_COLORS[1],
            50,  DENSITY_COLORS[2],
            75,  DENSITY_COLORS[3],
            100, DENSITY_COLORS[4],
          ],
          "fill-opacity": 0.65,
        },
      });

      mapObj.current.addLayer({
        id: "ward-outline",
        type: "line",
        source: "wards",
        paint: { "line-color": "#93C5FD", "line-width": 1 },
      });

      // Click → show tooltip
      mapObj.current.on("click", "ward-fill", (e: any) => {
        const props = e.features?.[0]?.properties;
        if (!props) return;
        import('maplibre-gl').then(mod => {
          new mod.default.Popup()
            .setLngLat(e.lngLat)
            .setHTML(`<strong>${props.name || "Ward"}</strong><br/>${props.complaint_count} complaint${props.complaint_count !== 1 ? "s" : ""}`)
            .addTo(mapObj.current);
        });
      });
      mapObj.current.on("mouseenter", "ward-fill", () => { mapObj.current.getCanvas().style.cursor = "pointer"; });
      mapObj.current.on("mouseleave", "ward-fill", () => { mapObj.current.getCanvas().style.cursor = ""; });

    } catch (err) {
      console.error("Ward heatmap error:", err);
      setWardError(true);
    }
  }, [category]);

  useEffect(() => {
    if (mapLoaded) loadWardData();
  }, [mapLoaded, loadWardData]);

  return (
    <div className="h-screen flex flex-col">
      {/* Category filter bar */}
      <div className="flex items-center gap-2 px-4 py-2 bg-white border-b border-gray-200 flex-wrap shrink-0">
        <span className="text-sm font-semibold text-gray-700 mr-1">Filter:</span>
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setCategory(cat === "All" ? undefined : cat.toLowerCase())}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              (cat === "All" && !category) || category === cat.toLowerCase()
                ? "bg-blue-700 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Map container */}
      <div className="flex-1 relative">
        <div ref={mapRef} className="absolute inset-0" />

        {/* Legend */}
        <div className="absolute bottom-6 left-4 bg-white rounded-xl border border-gray-200 p-3 shadow-md text-xs z-10">
          <p className="font-semibold text-gray-700 mb-2">Complaint Density</p>
          <div className="flex items-center gap-1">
            {DENSITY_COLORS.map((c, i) => (
              <div key={i} title={["None", "Low", "Med", "High", "Critical"][i]}
                   className="w-7 h-4 rounded" style={{ backgroundColor: c, border: "1px solid #e5e7eb" }} />
            ))}
          </div>
          <div className="flex justify-between mt-1 text-gray-400">
            <span>None</span><span>Critical</span>
          </div>
        </div>

        {wardError && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-amber-50 border border-amber-200 text-amber-800 text-xs px-3 py-2 rounded-lg shadow z-10">
            Ward boundary data unavailable — check backend connection.
          </div>
        )}
      </div>
    </div>
  );
}

