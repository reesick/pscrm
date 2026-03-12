import React, { useEffect, useRef } from 'react';
import 'maplibre-gl/dist/maplibre-gl.css';

export function ComplaintMap({ children, center = [77.2090, 28.6139], zoom = 11, onMapLoad }: { children?: React.ReactNode, center?: [number, number], zoom?: number, onMapLoad?: (map: any) => void }) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<any>(null);

  useEffect(() => {
    if (!mapRef.current) return;
    import('maplibre-gl').then(mod => {
      const maplibregl = mod.default;
      mapInstance.current = new maplibregl.Map({
        container: mapRef.current!,
        style: "https://tiles.openfreemap.org/styles/liberty",
        center,
        zoom,
      });
      
      mapInstance.current.on('load', () => {
        if (onMapLoad && mapInstance.current) {
          onMapLoad(mapInstance.current);
        }
      });
    });

    return () => {
      mapInstance.current?.remove();
    };
  }, []);

  return (
    <div ref={mapRef} className="w-full h-full relative">
      {children}
    </div>
  );
}
