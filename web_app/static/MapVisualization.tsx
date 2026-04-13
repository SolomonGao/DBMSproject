import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix default marker icon issue with Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

export interface EventData {
  id: number;
  date: string;
  lat: number;
  lng: number;
  actor1: string;
  actor2: string;
  goldsteinScale: number;
  location: string;
  description?: string;
}

interface MapVisualizationProps {
  events: EventData[];
}

export function MapVisualization({ events }: MapVisualizationProps) {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    // Initialize map centered on North America
    const map = L.map(mapContainerRef.current).setView([40, -95], 4);
    mapRef.current = map;

    // Add OpenStreetMap tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map);

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current || events.length === 0) return;

    // Clear existing markers
    mapRef.current.eachLayer((layer) => {
      if (layer instanceof L.Marker) {
        layer.remove();
      }
    });

    // Add markers for each event
    const bounds: L.LatLngBoundsLiteral = [];

    events.forEach((event) => {
      if (!event.lat || !event.lng) return;

      bounds.push([event.lat, event.lng]);

      // Determine marker color based on conflict intensity (GoldsteinScale)
      const getMarkerColor = (scale: number) => {
        if (scale < -5) return '#ef4444'; // red - severe conflict
        if (scale < 0) return '#f97316'; // orange - mild conflict
        if (scale < 5) return '#3b82f6'; // blue - cooperation
        return '#22c55e'; // green - strong cooperation
      };

      const color = getMarkerColor(event.goldsteinScale);

      // Create custom icon
      const customIcon = L.divIcon({
        className: 'custom-marker',
        html: `<div style="background-color: ${color}; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });

      const marker = L.marker([event.lat, event.lng], { icon: customIcon });

      // Create popup content
      const popupContent = `
        <div style="min-width: 200px;">
          <h3 style="font-weight: 600; margin-bottom: 8px; font-size: 14px;">${event.location}</h3>
          <p style="margin: 4px 0; font-size: 12px;"><strong>Date:</strong> ${event.date}</p>
          <p style="margin: 4px 0; font-size: 12px;"><strong>Actors:</strong> ${event.actor1} → ${event.actor2}</p>
          <p style="margin: 4px 0; font-size: 12px;"><strong>Intensity:</strong> ${event.goldsteinScale.toFixed(1)}</p>
          ${event.description ? `<p style="margin-top: 8px; font-size: 12px; color: #666;">${event.description}</p>` : ''}
        </div>
      `;

      marker.bindPopup(popupContent);
      marker.addTo(mapRef.current!);
    });

    // Fit map to show all markers
    if (bounds.length > 0) {
      mapRef.current.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [events]);

  return (
    <div className="w-full h-full rounded-lg overflow-hidden border border-gray-300">
      <div ref={mapContainerRef} className="w-full h-full min-h-[400px]" />
    </div>
  );
}
