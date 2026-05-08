import { MapPin, Minus, Plus } from 'lucide-react';

export function RoutePreview({ status = '正在规划路线' }) {
  return (
    <section className="route-preview" aria-label="路线预览">
      <div className="route-status">
        <span />
        {status}
      </div>
      <div className="phone-map" aria-hidden="true">
        <div className="map-topbar" />
        <div className="map-river" />
        <div className="map-route" />
        <MapPin className="map-pin pin-one" size={30} />
        <MapPin className="map-pin pin-two" size={30} />
        <MapPin className="map-pin pin-three" size={30} />
        <MapPin className="map-pin pin-four" size={30} />
        <div className="map-caption" />
      </div>
      <div className="map-zoom">
        <button type="button" aria-label="放大地图"><Plus size={19} /></button>
        <button type="button" aria-label="缩小地图"><Minus size={19} /></button>
      </div>
    </section>
  );
}
