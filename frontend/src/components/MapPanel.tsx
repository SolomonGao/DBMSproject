import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { GeoPoint } from '../types';

interface Props {
  data: GeoPoint[];
  title?: string;
}

export default function MapPanel({ data, title = 'Event Density Map' }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const layerGroup = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;

    const map = L.map(mapRef.current).setView([40, -95], 4);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 18,
    }).addTo(map);

    mapInstance.current = map;
    layerGroup.current = L.layerGroup().addTo(map);

    return () => {
      mapInstance.current?.remove();
      mapInstance.current = null;
      layerGroup.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapInstance.current || !layerGroup.current) return;

    layerGroup.current.clearLayers();
    if (data.length === 0) return;

    const bounds: L.LatLngExpression[] = [];

    data.forEach((point) => {
      bounds.push([point.lat, point.lng]);

      const color = point.avg_conflict !== undefined
        ? point.avg_conflict < -5 ? '#dc2626'
        : point.avg_conflict < 0 ? '#f97316'
        : '#3b82f6'
        : '#6b7280';

      const radius = Math.max(4, Math.min(20, Math.sqrt(point.intensity) * 2));

      const circle = L.circleMarker([point.lat, point.lng], {
        radius,
        fillColor: color,
        color: '#fff',
        weight: 1,
        opacity: 1,
        fillOpacity: 0.7,
      });

      circle.bindPopup(`
        <div style="font-size:12px">
          <strong>${point.sample_location || 'Unknown'}</strong><br/>
          Intensity: ${point.intensity}<br/>
          Avg Conflict: ${point.avg_conflict?.toFixed(2) ?? 'N/A'}
        </div>
      `);

      circle.addTo(layerGroup.current!);
    });

    if (bounds.length > 0) {
      mapInstance.current.fitBounds(bounds as L.LatLngExpression[], { padding: [40, 40] });
    }
  }, [data]);

  return (
    <div className="panel">
      <h3>{title}</h3>
      <div ref={mapRef} style={{ width: '100%', height: 400, borderRadius: 8 }} />
    </div>
  );
}
