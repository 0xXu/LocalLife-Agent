/**
 * POI data service — all data comes from backend GET /api/route/pois.
 * No frontend mock data. Backend MockDataService is the single source of truth.
 */
(function() {
  // ─── Cached POI data per city ──────────────────────────────────
  var _poiCache = {};       // city → POI dictionary (keyed by name)
  var _poiListCache = {};   // city → POI array
  var _loading = {};        // city → Promise (prevents duplicate fetches)

  // ─── Adapt backend POI to frontend format ──────────────────────
  function adaptPOI(p) {
    return {
      id: p.id,
      name: p.name,
      short: p.name,
      category: p.subCategory || p.category || '',
      subcategory: p.subCategory || '',
      rating: p.rating || 0,
      review_count: 0,
      avg_price: p.avgCost || 0,
      opening_hours: '',
      current_status: '营业中',
      current_status_short: '营业中',
      status_tone: 'green',
      wait_time: (p.queueTime > 10) ? '约 ' + p.queueTime + ' 分钟' : '无需排队',
      tags: p.tags || [],
      ugcTags: p.ugcTags || [],
      ugcSummary: p.ugcSummary || '',
      risk_tags: p.riskTags || [],
      recommendation_reason: p.description || '',
      review_summary: p.ugcSummary || (p.tags || []).join('、'),
      lng: p.lng,
      lat: p.lat,
      imageUrl: p.imageUrl || '',
      images: p.imageUrl ? [p.imageUrl] : [],
      address: p.address || '',
      city: p.city || '',
      district: p.district || '',
      targetAudience: [],
      bestTime: '',
      duration: '',
      mock_x: Math.round(((p.lng - 115.5) / (122 - 115.5)) * 100),
      mock_y: Math.round(((41 - p.lat) / (41 - 30.5)) * 100),
    };
  }

  // ─── Fetch POIs from backend ───────────────────────────────────
  async function fetchPOIs(city) {
    city = city || '北京';
    if (_loading[city]) return _loading[city];

    _loading[city] = (async function() {
      try {
        var API_BASE = window.API_BASE || (window.location.hostname === 'localhost' ? 'http://localhost:8081' : '');
        var url = API_BASE + '/api/route/pois?city=' + encodeURIComponent(city);
        var res = await (window.fetchWithTimeout || fetch)(url, {}, 10000);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        var pois = await res.json();
        if (!pois || pois.length < 5) throw new Error('Insufficient POIs: ' + (pois ? pois.length : 0));

        var dict = {};
        var list = [];
        pois.forEach(function(p) {
          var adapted = adaptPOI(p);
          var key = p.name;
          var suffix = p.district ? ' (' + p.district + ')' : '';
          var counter = 0;
          while (dict[key]) {
            counter++;
            key = p.name + suffix + (counter > 1 ? ' ' + counter : '');
            if (counter > 50) { key = p.id || ('poi-' + Date.now() + '-' + Math.random()); break; }
          }
          dict[key] = adapted;
          list.push(adapted);
        });

        _poiCache[city] = dict;
        _poiListCache[city] = list;
        console.log('[POI] Loaded ' + list.length + ' POIs from backend for ' + city);
        return { dict: dict, list: list };
      } catch (e) {
        console.error('[POI] Backend POI fetch failed for ' + city + ':', e.message);
        _loading[city] = null;
        // Return empty result instead of throwing — prevents app freeze
        // when backend is running but POI endpoint has issues
        _poiCache[city] = {};
        _poiListCache[city] = [];
        return { dict: {}, list: [] };
      }
    })();

    return _loading[city];
  }

  // ─── Sync (preload) for a city — returns Promise ──────────────
  window.preloadPOIs = function(city) {
    return fetchPOIs(city).then(function() { return true; }).catch(function() { return false; });
  };

  // ─── Get POI dictionary for a city (async) ────────────────────
  window.getPlacesByCityAsync = async function(city) {
    city = city || window._currentCity || '北京';
    if (_poiCache[city]) return _poiCache[city];
    var result = await fetchPOIs(city);
    return result.dict;
  };

  // ─── Get POI list for a city (async) ───────────────────────────
  window.getPOIListAsync = async function(city) {
    city = city || window._currentCity || '北京';
    if (_poiListCache[city]) return _poiListCache[city];
    var result = await fetchPOIs(city);
    return result.list;
  };

  // ─── Sync getPlacesByCity (returns cached data or empty if not loaded) ──
  window.getPlacesByCity = function(city) {
    city = city || window._currentCity || '北京';
    return _poiCache[city] || {};
  };

  // ─── Get places for a route (looks up cached POIs by name) ────
  window.getPlacesForRoute = function(route, city) {
    var effectiveCity = city || window._currentCity || '北京';
    var dict = _poiCache[effectiveCity] || {};

    if (route && route._raw && route._raw.segments) {
      return route._raw.segments.map(function(seg) {
        var poi = seg.poi || {};
        var name = poi.name || '';
        var cached = dict[name] || dict[poi.id] || null;
        if (cached) return Object.assign({}, cached, { name: name, short: name });
        // Build minimal POI from route data (backend already includes full info)
        return {
          id: poi.id || '', name: name, short: name,
          category: poi.subCategory || poi.category || '',
          rating: poi.rating || 0, avg_price: poi.avgCost || 0,
          tags: poi.tags || [], risk_tags: poi.riskTags || [],
          ugcTags: poi.ugcTags || [], ugcSummary: poi.ugcSummary || '',
          imageUrl: poi.imageUrl || '', images: poi.imageUrl ? [poi.imageUrl] : [],
          lng: poi.lng, lat: poi.lat, address: poi.address || '',
          city: effectiveCity, district: poi.district || '',
          mock_x: Math.round(((poi.lng - 115.5) / (122 - 115.5)) * 100),
          mock_y: Math.round(((41 - poi.lat) / (41 - 30.5)) * 100),
        };
      });
    }

    // Fallback: build from route.pois
    if (route && route.pois) {
      return route.pois.map(function(p, i) {
        var name = p.short || p.name || ('地点' + (i + 1));
        var cached = dict[name];
        if (cached) return Object.assign({}, cached);
        return { id: 'poi-' + i, name: name, short: name, category: p.category || '',
                 rating: p.rating || 0, avg_price: p.avgCost || 0,
                 ugcSummary: p.ugcSummary || '', risk_tags: p.riskTags || [] };
      });
    }

    return [];
  };

  // ─── Refresh MOCK_PLACES for route detail display ──────────────
  window.refreshMockPlaces = async function(city) {
    city = city || window._currentCity || '北京';
    try {
      var list = await window.getPOIListAsync(city);
      // Build showcase: pick a few representative POIs for the detail page map
      window.MOCK_PLACES = list.slice(0, 6).map(function(p, i) {
        return Object.assign({}, p, {
          distance: i === 0 ? '距出发地' : '距上一站 ' + (300 + i * 400) + 'm',
          current_status: '营业中',
        });
      });
      return window.MOCK_PLACES;
    } catch (e) {
      window.MOCK_PLACES = [];
      return [];
    }
  };

  // ─── Initial load — deferred to avoid blocking page render ──────
  // Delay by 2s to let React mount first, then fetch POIs in background
  setTimeout(function() {
    window.preloadPOIs(window._currentCity || '北京').then(function() {
      try { window.refreshMockPlaces(window._currentCity); } catch(ignore) {}
    }).catch(function() {});  // Silently fail — backend may not be ready yet
  }, 2000);

  // Re-fetch on city change — debounced to avoid rapid duplicate fetches
  var _currentCityValue = window._currentCity;
  var _preloadTimer = null;

  // Safe direct setter — used by app.jsx to bypass Object.defineProperty
  // and set the internal value without triggering a redundant preload
  window._setCityDirectly = function(v) {
    _currentCityValue = v;
  };

  Object.defineProperty(window, '_currentCity', {
    get: function() { return _currentCityValue; },
    set: function(v) {
      _currentCityValue = v;
      if (_preloadTimer) clearTimeout(_preloadTimer);
      _preloadTimer = setTimeout(function() {
        window.preloadPOIs(v).then(function() {
          try { window.refreshMockPlaces(v); } catch(ignore) {}
        }).catch(function() {});
      }, 500);
    },
    configurable: true, enumerable: true,
  });
})();
