/**
 * mapIntegration.js
 * 前端地图集成模块 - 为GDELT项目添加地图可视化
 * 无依赖，即插即用
 */

class GDELTMapIntegration {
    constructor(containerId = 'mapContainer') {
        this.containerId = containerId;
        this.mapInstance = null;
        this.markers = [];
        this.events = [];
        this.initialized = false;
    }

    /**
     * 初始化地图（第一次加载时调用）
     */
    init() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.warn(`Map container #${this.containerId} not found`);
            return false;
        }

        try {
            // 检查Leaflet是否加载
            if (typeof L === 'undefined') {
                console.warn('Leaflet not loaded');
                return false;
            }

            // 初始化地图
            this.mapInstance = L.map(this.containerId).setView([39, -98], 4);
            
            // 添加地图图层
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap',
                maxZoom: 18,
            }).addTo(this.mapInstance);

            this.initialized = true;
            console.log('[Map] Initialized successfully');
            return true;
        } catch (e) {
            console.error('[Map] Initialization failed:', e);
            return false;
        }
    }

    /**
     * 显示/隐藏地图
     */
    toggle(show) {
        const container = document.getElementById(this.containerId);
        if (!container) return;

        if (show) {
            container.style.display = 'block';
            if (this.mapInstance) {
                this.mapInstance.invalidateSize();
            }
        } else {
            container.style.display = 'none';
        }
    }

    /**
     * 从LLM响应中提取事件并显示
     * 支持的格式：
     * 1. "城市 (lat, lng): 事件描述"
     * 2. JSON: {"location": "城市", "lat": 40, "lng": -74, ...}
     */
    showEventsFromText(text) {
        if (!this.mapInstance) {
            console.warn('[Map] Map not initialized');
            return;
        }

        const events = this.extractEvents(text);
        this.visualize(events);
    }

    /**
     * 智能提取事件
     */
    extractEvents(text) {
        const events = [];

        // 模式1: "城市 (lat, lng): 描述"
        const pattern1 = /([A-Za-z\s,]+?)\s*\((-?\d+\.?\d*),\s*(-?\d+\.?\d*)\):\s*([^\n]+)/g;
        let match;
        while ((match = pattern1.exec(text)) !== null) {
            events.push({
                location: match[1].trim(),
                lat: parseFloat(match[2]),
                lng: parseFloat(match[3]),
                description: match[4].trim(),
            });
        }

        // 模式2: 城市名称查找（内置美国主要城市）
        const cities = {
            'New York': [40.7128, -74.0060],
            'Los Angeles': [34.0522, -118.2437],
            'Chicago': [41.8781, -87.6298],
            'Houston': [29.7604, -95.3698],
            'Phoenix': [33.4484, -112.0742],
            'Philadelphia': [39.9526, -75.1652],
            'San Antonio': [29.4241, -98.4936],
            'San Diego': [32.7157, -117.1611],
            'Dallas': [32.7767, -96.7970],
            'San Jose': [37.3382, -121.8863],
            'Austin': [30.2672, -97.7431],
            'Jacksonville': [30.3322, -81.6557],
            'Fort Worth': [32.7555, -97.3308],
            'Columbus': [39.9612, -82.9988],
            'Charlotte': [35.2271, -80.8431],
            'San Francisco': [37.7749, -122.4194],
            'Indiana': [39.7684, -86.1581],
            'Seattle': [47.6062, -122.3321],
            'Denver': [39.7392, -104.9903],
            'Boston': [42.3601, -71.0589],
            'Washington': [38.9072, -77.0369],
            'Miami': [25.7617, -80.1918],
            'Atlanta': [33.7490, -84.3880],
            'Las Vegas': [36.1699, -115.1398],
            'Detroit': [42.3314, -83.0458],
            'Minnesota': [44.9778, -93.2650],
            'Portland': [45.5152, -122.6784],
            'Baltimore': [39.2904, -76.6122],
            'Louisville': [38.2527, -85.7585],
            'Milwaukee': [43.0389, -87.9065],
            'Albuquerque': [35.0844, -106.6504],
            'Tucson': [32.2226, -110.9747],
            'Oklahoma': [35.4676, -97.5164],
            'Texas': [31.9686, -99.9018],
            'California': [36.7783, -119.4179],
            'Florida': [27.6648, -81.5158],
        };

        // 在文本中查找城市名
        for (const [city, coords] of Object.entries(cities)) {
            const regex = new RegExp(city, 'gi');
            if (regex.test(text)) {
                // 检查是否已添加
                if (!events.some(e => e.location === city)) {
                    events.push({
                        location: city,
                        lat: coords[0],
                        lng: coords[1],
                        description: `${city} conflict event`,
                    });
                }
            }
        }

        return events;
    }

    /**
     * 在地图上可视化事件
     */
    visualize(events) {
        if (!this.mapInstance) return;

        // 清空旧标记
        this.markers.forEach(marker => {
            this.mapInstance.removeLayer(marker);
        });
        this.markers = [];
        this.events = events;

        if (events.length === 0) {
            console.log('[Map] No events to display');
            return;
        }

        const bounds = [];

        events.forEach((event, index) => {
            if (!event.lat || !event.lng) return;

            bounds.push([event.lat, event.lng]);

            // 创建标记
            const icon = L.divIcon({
                className: 'map-marker',
                html: `<div class="marker-bubble" style="
                    background-color: #ef4444;
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    border: 3px solid white;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-weight: bold;
                    font-size: 14px;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.4);
                ">${index + 1}</div>`,
                iconSize: [32, 32],
                iconAnchor: [16, 16],
            });

            const marker = L.marker([event.lat, event.lng], { icon })
                .bindPopup(`
                    <div style="font-size: 12px; min-width: 200px;">
                        <h4 style="margin: 0 0 8px 0; font-weight: bold;">${event.location}</h4>
                        <p style="margin: 4px 0;"><strong>描述:</strong> ${event.description}</p>
                        <p style="margin: 4px 0;"><strong>坐标:</strong> (${event.lat.toFixed(2)}, ${event.lng.toFixed(2)})</p>
                    </div>
                `)
                .addTo(this.mapInstance);

            this.markers.push(marker);
        });

        // 自动缩放到所有标记
        if (bounds.length > 0) {
            try {
                this.mapInstance.fitBounds(bounds, { padding: [50, 50], maxZoom: 10 });
            } catch (e) {
                console.warn('[Map] Could not fit bounds:', e);
            }
        }

        console.log(`[Map] Displayed ${events.length} events`);
    }

    /**
     * 清空地图
     */
    clear() {
        this.markers.forEach(marker => {
            this.mapInstance.removeLayer(marker);
        });
        this.markers = [];
        this.events = [];
    }

    /**
     * 获取当前事件
     */
    getEvents() {
        return this.events;
    }
}

// 全局实例
window.gdeltMap = new GDELTMapIntegration('mapContainer');
