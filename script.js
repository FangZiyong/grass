// ==UserScript==
// @name         IKCRM 路线距离&费用自动计算（高德地图）
// @namespace    https://e.ikcrm.com/
// @version      1.0.0
// @description  右下角弹窗：起点/途经/终点可输入+联想下拉+拖拽排序，一键查询驾车距离与费用（高德 WebService）
// @author       You
// @match        https://e.ikcrm.com/*
// @grant        GM_addStyle
// @grant        GM_xmlhttpRequest
// @connect      restapi.amap.com
// ==/UserScript==

(function () {
  "use strict";

  /***********************
   * 配置区
   ***********************/
  const AMAP_KEY = "945b9fa6d3096d6dc0bef27f40f9df1a";

  // API
  const API_PLACE_TEXT = "https://restapi.amap.com/v3/place/text";
  const API_DRIVING = "https://restapi.amap.com/v5/direction/driving";

  // UI 本地存储 key
  const STORAGE_KEY = "__ikcrm_route_helper_state_v1__";
  const STORAGE_FAVORITES_KEY = "__ikcrm_route_helper_favorites_v1__";

  /***********************
   * 工具函数
   ***********************/
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function debounce(fn, wait = 300) {
    let t = null;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  }

  function uid(prefix = "id") {
    return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`;
  }

  function safeJsonParse(text) {
    try {
      return JSON.parse(text);
    } catch (e) {
      return null;
    }
  }

  function isLngLatLike(s) {
    if (!s) return false;
    return /^\s*[-+]?\d+(\.\d+)?\s*,\s*[-+]?\d+(\.\d+)?\s*$/.test(String(s));
  }

  function normalizeLngLat(s) {
    // 保留 6 位小数（高德建议 <=6）更稳定
    const [lng, lat] = String(s)
      .split(",")
      .map((x) => Number(String(x).trim()));
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return null;
    const lngFixed = Math.round(lng * 1e6) / 1e6;
    const latFixed = Math.round(lat * 1e6) / 1e6;
    return `${lngFixed},${latFixed}`;
  }

  function formatDistanceMeters(m) {
    const mm = Number(m);
    if (!Number.isFinite(mm)) return "-";
    const km = mm / 1000;
    if (km < 1) return `${mm.toFixed(0)} m`;
    return `${km.toFixed(2)} km`;
  }

  function formatMoneyYuan(y) {
    const yy = Number(y);
    if (!Number.isFinite(yy)) return "-";
    return `${yy.toFixed(1)} 元`;
  }

  function formatDurationSec(sec) {
    const s = Number(sec);
    if (!Number.isFinite(s)) return "-";
    const mins = Math.round(s / 60);
    if (mins < 60) return `${mins} 分钟`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h} 小时 ${m} 分钟`;
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const obj = JSON.parse(raw);
      if (!obj || typeof obj !== "object") return null;
      return obj;
    } catch (e) {
      return null;
    }
  }

  function saveState(state) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {}
  }

  function gmGetJSON(url) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: "GET",
        url,
        timeout: 12000,
        onload: (res) => {
          const data = safeJsonParse(res.responseText);
          if (!data) return reject(new Error("接口返回无法解析 JSON"));
          resolve(data);
        },
        onerror: () => reject(new Error("网络请求失败")),
        ontimeout: () => reject(new Error("请求超时")),
      });
    });
  }

  /***********************
   * 高德：地点搜索（使用 place/text 接口）
   ***********************/
  async function searchPlace(keywords) {
    // 官方参数：key + keywords + output=JSON
    // 可选：city, citylimit, offset, page
    const url =
      `${API_PLACE_TEXT}?key=${encodeURIComponent(AMAP_KEY)}` +
      `&keywords=${encodeURIComponent(keywords)}` +
      `&output=JSON` +
      `&offset=20` +
      `&page=1`;
    const data = await gmGetJSON(url);

    if (data.status !== "1") {
      const msg = data.info || "地点搜索失败";
      throw new Error(msg);
    }
    const list = Array.isArray(data.pois) ? data.pois : [];
    // 显示最多 8 条
    return list.slice(0, 8).map((poi) => {
      const loc = poi.location || "";
      const niceLoc = isLngLatLike(loc) ? normalizeLngLat(loc) : loc;

      // 使用 POI 名称和地址
      const city = String(poi.cityname || poi.city || "").trim();
      const rawName = poi.name || keywords;
      const name = city ? `【${city}】${rawName}` : rawName;
      const address = poi.address || "";
      const fullName = address ? `${name}（${address}）` : name;

      return {
        name: fullName,
        location: niceLoc,
        raw: poi,
      };
    }).filter((x) => x.location && isLngLatLike(x.location));
  }

  /***********************
   * 收藏地点管理
   ***********************/
  function loadFavorites() {
    try {
      const raw = localStorage.getItem(STORAGE_FAVORITES_KEY);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch (e) {
      return [];
    }
  }

  function saveFavorites(favorites) {
    try {
      localStorage.setItem(STORAGE_FAVORITES_KEY, JSON.stringify(favorites));
    } catch (e) {}
  }

  function addFavorite(name, location) {
    const favorites = loadFavorites();
    // 检查是否已存在
    const exists = favorites.some((f) => f.location === location);
    if (exists) return false;
    favorites.push({ name, location, id: uid("fav") });
    saveFavorites(favorites);
    return true;
  }

  function removeFavorite(location) {
    const favorites = loadFavorites();
    const filtered = favorites.filter((f) => f.location !== location);
    saveFavorites(filtered);
    return filtered.length !== favorites.length;
  }

  function isFavorited(location) {
    if (!location) return false;
    return loadFavorites().some((f) => f.location === location);
  }

  function toggleFavorite(name, location) {
    if (!location || !isLngLatLike(location)) return false;
    if (isFavorited(location)) {
      removeFavorite(location);
      return false;
    }
    addFavorite(name || location, location);
    return true;
  }

  /***********************
   * 高德：路径规划（驾车）
   ***********************/
  async function drivingRoute({ origin, destination, waypoints = [] }) {
    // v5/direction/driving
    // 必填：origin destination key
    // 可选：waypoints（分号分隔） show_fields=cost
    const wp = waypoints.length ? waypoints.join(";") : "";
    const url =
      `${API_DRIVING}?key=${encodeURIComponent(AMAP_KEY)}` +
      `&origin=${encodeURIComponent(origin)}` +
      `&destination=${encodeURIComponent(destination)}` +
      (wp ? `&waypoints=${encodeURIComponent(wp)}` : "") +
      `&strategy=32` +
      `&show_fields=cost`;

    const data = await gmGetJSON(url);

    if (data.status !== "1") {
      const msg = data.info || "路径规划失败";
      throw new Error(msg);
    }

    const route = data.route || {};
    const paths = Array.isArray(route.paths) ? route.paths : [];
    if (!paths.length) throw new Error("未返回可用路线");

    const p0 = paths[0];
    const distance = p0.distance; // 米
    const cost = p0.cost || {};
    const tolls = cost.tolls; // 元（可能为空）
    const duration = cost.duration || p0.duration; // 秒（show_fields=cost 才保证有）
    const taxiCost = route.taxi_cost; // 元（字符串）

    // primary cost：优先过路费（tolls），否则用 taxi_cost
    const primaryCost = (tolls !== undefined && tolls !== null && String(tolls).length)
      ? tolls
      : taxiCost;

    return {
      distance,
      tolls,
      taxiCost,
      duration,
      primaryCost,
      raw: data,
    };
  }

  /***********************
   * UI 注入
   ***********************/
  GM_addStyle(`
    :root {
      --ikrh-bg: rgba(255,255,255,.92);
      --ikrh-card: rgba(255,255,255,.96);
      --ikrh-text: #111827;
      --ikrh-sub: #6b7280;
      --ikrh-border: rgba(0,0,0,.08);
      --ikrh-shadow: 0 18px 60px rgba(0,0,0,.18);
      --ikrh-shadow-soft: 0 10px 30px rgba(0,0,0,.12);
      --ikrh-primary: #2563eb;
      --ikrh-primary2: #1d4ed8;
      --ikrh-danger: #ef4444;
      --ikrh-ok: #10b981;
      --ikrh-warn: #f59e0b;
      --ikrh-radius: 16px;
      --ikrh-radius2: 12px;
      --ikrh-font: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
    }

    #ikcrm-route-helper {
      position: fixed;
      right: 18px;
      bottom: 18px;
      z-index: 999999;
      font-family: var(--ikrh-font);
      color: var(--ikrh-text);
    }

    .ikrh-fab {
      width: 52px;
      height: 52px;
      border-radius: 999px;
      border: 1px solid var(--ikrh-border);
      background: linear-gradient(180deg, #ffffff, rgba(255,255,255,.75));
      box-shadow: var(--ikrh-shadow-soft);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      user-select: none;
      transition: transform .15s ease, box-shadow .15s ease;
    }
    .ikrh-fab:hover { transform: translateY(-2px); box-shadow: var(--ikrh-shadow); }
    .ikrh-fab:active { transform: translateY(0px); }

    .ikrh-fab svg {
      width: 24px;
      height: 24px;
      color: var(--ikrh-primary);
    }

    .ikrh-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.4);
      backdrop-filter: blur(4px);
      z-index: 999998;
      display: none;
      animation: ikrhFadeIn .15s ease-out;
    }
    .ikrh-overlay.open { display: block; }
    @keyframes ikrhFadeIn { from { opacity: 0; } to { opacity: 1; } }

    .ikrh-panel {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 900px;
      max-width: min(900px, calc(100vw - 32px));
      max-height: min(85vh, 720px);
      border: 1px solid var(--ikrh-border);
      background: var(--ikrh-bg);
      backdrop-filter: blur(10px);
      border-radius: var(--ikrh-radius);
      box-shadow: var(--ikrh-shadow);
      overflow: visible;
      display: none;
      z-index: 999999;
    }

    .ikrh-panel-layout {
      display: flex;
      height: 100%;
      max-height: min(85vh, 720px);
    }

    .ikrh-panel-left {
      flex: 1;
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--ikrh-border);
      overflow: visible;
    }

    .ikrh-panel-right {
      width: 320px;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      background: rgba(255,255,255,.5);
      overflow: hidden;
    }

    .ikrh-panel.open { display: block; animation: ikrhModalIn .18s ease-out; }
    @keyframes ikrhModalIn { from { transform: translate(-50%, -50%) scale(0.95); opacity: 0.6; } to { transform: translate(-50%, -50%) scale(1); opacity: 1; } }

    .ikrh-header {
      padding: 14px 14px 12px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--ikrh-border);
      background: linear-gradient(180deg, rgba(255,255,255,.95), rgba(255,255,255,.70));
    }

    .ikrh-title {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
      letter-spacing: .2px;
    }
    .ikrh-badge {
      font-size: 12px;
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid var(--ikrh-border);
      color: var(--ikrh-sub);
      background: rgba(255,255,255,.75);
    }

    .ikrh-close {
      width: 32px;
      height: 32px;
      border-radius: 10px;
      border: 1px solid var(--ikrh-border);
      background: rgba(255,255,255,.8);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform .15s ease;
    }
    .ikrh-close:hover { transform: scale(1.02); }

    .ikrh-body {
      padding: 14px;
      overflow: visible;
      flex: 1;
    }

    .ikrh-body-left {
      padding: 14px;
      overflow: visible;
      flex: 1;
    }

    .ikrh-body-right {
      padding: 14px;
      overflow-y: auto;
      flex: 1;
    }

    .ikrh-hint {
      font-size: 12px;
      color: var(--ikrh-sub);
      line-height: 1.35;
      margin-bottom: 12px;
    }

    .ikrh-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-bottom: 12px;
    }

    .ikrh-stop {
      border: 1px solid var(--ikrh-border);
      background: var(--ikrh-card);
      border-radius: var(--ikrh-radius2);
      padding: 8px 10px;
      box-shadow: 0 2px 8px rgba(0,0,0,.04);
      display: flex;
      align-items: center;
      gap: 8px;
      transition: box-shadow .15s ease;
    }
    .ikrh-stop:hover {
      box-shadow: 0 4px 12px rgba(0,0,0,.08);
    }

    .ikrh-stop-left {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      flex: 1;
    }

    .ikrh-drag {
      width: 24px;
      height: 24px;
      border-radius: 6px;
      border: 1px solid var(--ikrh-border);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: grab;
      user-select: none;
      color: var(--ikrh-sub);
      background: rgba(255,255,255,.9);
      flex-shrink: 0;
      font-size: 14px;
    }
    .ikrh-drag:active {
      cursor: grabbing;
    }

    .ikrh-stop-num {
      font-size: 13px;
      font-weight: 700;
      color: var(--ikrh-text);
      min-width: 20px;
      text-align: center;
    }

    .ikrh-input-wrap {
      position: relative;
      flex: 1;
      min-width: 0;
    }

    .ikrh-clear {
      border: 1px solid var(--ikrh-border);
      background: rgba(255,255,255,.9);
      color: var(--ikrh-sub);
      border-radius: 10px;
      width: 30px;
      height: 30px;
      cursor: pointer;
    }

    .ikrh-input {
      width: 100%;
      box-sizing: border-box;
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid var(--ikrh-border);
      background: rgba(255,255,255,.9);
      outline: none;
      font-size: 13px;
      transition: box-shadow .15s ease, border-color .15s ease;
    }
    .ikrh-input:focus {
      border-color: rgba(37,99,235,.45);
      box-shadow: 0 0 0 3px rgba(37,99,235,.12);
    }


    .ikrh-stop-actions {
      display: flex;
      gap: 6px;
      align-items: center;
      flex-shrink: 0;
    }

    .ikrh-delete {
      border: 1px solid var(--ikrh-border);
      background: rgba(239,68,68,.1);
      color: var(--ikrh-danger);
      border-radius: 10px;
      width: 30px;
      height: 30px;
      cursor: pointer;
      font-size: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform .12s ease, background .12s ease;
    }
    .ikrh-delete:hover { transform: scale(1.05); background: rgba(239,68,68,.2); }

    .ikrh-add-waypoint {
      margin-top: 8px;
      padding: 8px 12px;
      border-radius: 12px;
      border: 1px dashed var(--ikrh-border);
      background: rgba(255,255,255,.6);
      color: var(--ikrh-sub);
      cursor: pointer;
      font-size: 12px;
      text-align: center;
      transition: all .15s ease;
    }
    .ikrh-add-waypoint:hover {
      border-color: var(--ikrh-primary);
      background: rgba(37,99,235,.08);
      color: var(--ikrh-primary);
    }

    .ikrh-dropdown {
      position: absolute;
      left: 0;
      right: 0;
      top: 38px;
      border-radius: 12px;
      border: 1px solid var(--ikrh-border);
      background: rgba(255,255,255,.95);
      box-shadow: 0 12px 40px rgba(0,0,0,.12);
      overflow: hidden;
      z-index: 20;
    }
    .ikrh-dd-item {
      padding: 10px 12px;
      cursor: pointer;
      border-bottom: 1px solid rgba(0,0,0,.05);
      font-size: 13px;
      line-height: 1.2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .ikrh-dd-item:last-child { border-bottom: none; }
    .ikrh-dd-item:hover { background: rgba(37,99,235,.08); }

    .ikrh-dd-item-content {
      flex: 1;
      min-width: 0;
      display: flex;
      align-items: center;
      white-space: nowrap;
      overflow: hidden;
    }
    .ikrh-dd-item-name {
      font-weight: 700;
      color: #111827;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
    }

    .ikrh-dd-group {
      padding: 6px 0;
    }

    .ikrh-dd-group-title {
      font-size: 11px;
      color: var(--ikrh-sub);
      padding: 6px 12px;
      background: rgba(0,0,0,.02);
      border-bottom: 1px solid rgba(0,0,0,.05);
    }

    .ikrh-dd-item-fav {
      width: 24px;
      height: 24px;
      border-radius: 6px;
      border: 1px solid var(--ikrh-border);
      background: rgba(255,255,255,.9);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      font-size: 12px;
      color: var(--ikrh-sub);
      transition: all .15s ease;
    }
    .ikrh-dd-item-fav:hover {
      background: rgba(37,99,235,.1);
      border-color: var(--ikrh-primary);
      color: var(--ikrh-primary);
    }
    .ikrh-dd-item-fav.favorited {
      background: rgba(245,158,11,.15);
      border-color: var(--ikrh-warn);
      color: var(--ikrh-warn);
    }

    .ikrh-actions {
      display: flex;
      gap: 10px;
      margin-top: 12px;
      align-items: center;
    }

    .ikrh-btn {
      flex: 1;
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid var(--ikrh-border);
      cursor: pointer;
      font-weight: 700;
      background: rgba(255,255,255,.9);
      transition: transform .15s ease, box-shadow .15s ease;
    }
    .ikrh-btn:hover { transform: translateY(-1px); box-shadow: 0 10px 24px rgba(0,0,0,.12); }

    .ikrh-btn-primary {
      background: linear-gradient(180deg, rgba(37,99,235,1), rgba(29,78,216,1));
      color: white;
      border-color: rgba(37,99,235,.45);
    }

    .ikrh-btn-secondary {
      background: rgba(255,255,255,.9);
      color: var(--ikrh-text);
    }

    .ikrh-result {
      margin-top: 12px;
      border: 1px solid var(--ikrh-border);
      background: rgba(255,255,255,.9);
      border-radius: 14px;
      padding: 12px;
    }

    .ikrh-result-top {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }

    .ikrh-metric {
      border: 1px solid rgba(0,0,0,.06);
      background: rgba(255,255,255,.9);
      border-radius: 14px;
      padding: 10px;
    }
    .ikrh-metric .k { font-size: 12px; color: var(--ikrh-sub); margin-bottom: 6px; }
    .ikrh-metric .v { font-size: 18px; font-weight: 800; letter-spacing: .2px; }

    .ikrh-result-sub {
      margin-top: 10px;
      font-size: 12px;
      color: var(--ikrh-sub);
      display: grid;
      gap: 6px;
    }

    .ikrh-toast {
      margin-top: 10px;
      font-size: 12px;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--ikrh-border);
      background: rgba(255,255,255,.9);
      color: var(--ikrh-sub);
    }

    .ikrh-toast.ok { border-color: rgba(16,185,129,.35); color: #047857; background: rgba(16,185,129,.08); }
    .ikrh-toast.err { border-color: rgba(239,68,68,.35); color: #b91c1c; background: rgba(239,68,68,.08); }
    .ikrh-toast.warn { border-color: rgba(245,158,11,.35); color: #92400e; background: rgba(245,158,11,.10); }

    .ikrh-stop.dragging { opacity: .55; }
    .ikrh-stop.drop-target { outline: 2px dashed rgba(37,99,235,.55); outline-offset: 4px; }
  `);

  /***********************
   * 状态
   ***********************/
  const defaultStops = () => ([
    { id: uid("stop"), text: "", location: "", suggestions: [], loading: false, showFavorites: false },
    { id: uid("stop"), text: "", location: "", suggestions: [], loading: false, showFavorites: false },
  ]);

  const state = {
    open: false,
    stops: defaultStops(),
    result: null,
    toast: null, // {type:'ok'|'err'|'warn', text:''}
    querying: false,
  };

  // 恢复本地历史
  const saved = loadState();
  if (saved?.stops && Array.isArray(saved.stops) && saved.stops.length >= 2) {
    state.stops = saved.stops.map((s) => ({
      id: uid("stop"),
      text: String(s.text || ""),
      location: String(s.location || ""),
      suggestions: [],
      loading: false,
      showFavorites: false,
    }));
  }

  function persist() {
    saveState({
      stops: state.stops.map((s) => ({ text: s.text, location: s.location })),
    });
  }

  /***********************
   * DOM 构建
   ***********************/
  const root = document.createElement("div");
  root.id = "ikcrm-route-helper";

  const overlay = document.createElement("div");
  overlay.className = "ikrh-overlay";

  const fab = document.createElement("div");
  fab.className = "ikrh-fab";
  fab.title = "路线查询";
  fab.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none">
      <path d="M7 3h10a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H9a2 2 0 0 0-2 2v6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      <circle cx="7" cy="3.5" r="2.2" stroke="currentColor" stroke-width="2"/>
      <circle cx="7" cy="21" r="2.2" stroke="currentColor" stroke-width="2"/>
      <path d="M9.5 9.5h7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </svg>
  `;

  const panel = document.createElement("div");
  panel.className = "ikrh-panel";
  panel.innerHTML = `
    <div class="ikrh-header">
      <div class="ikrh-title">
        <span>路线距离 & 费用</span>
        <span class="ikrh-badge">高德API</span>
      </div>
      <button class="ikrh-close" aria-label="close">✕</button>
    </div>
    <div class="ikrh-body">
      <div class="ikrh-panel-layout">
        <div class="ikrh-panel-left">
          <div class="ikrh-body-left">
            <div class="ikrh-hint">
              ① 输入地址会自动请求高德地点搜索并给出下拉候选<br/>
              ② 下拉里可收藏常用地点，常用地点会单独分组显示<br/>
              ③ 可拖拽调整顺序：第1个=起点，最后1个=终点，中间=途经<br/>
              ④ 点击"添加途径点"可增加更多地点
            </div>

            <div class="ikrh-list"></div>

            <div class="ikrh-actions">
              <button class="ikrh-btn ikrh-btn-secondary" data-act="reset">重置</button>
            </div>

            <div class="ikrh-toast" style="display:none;"></div>
          </div>
        </div>
        <div class="ikrh-panel-right">
          <div class="ikrh-body-right">
            <div class="ikrh-result" style="display:none;"></div>
          </div>
        </div>
      </div>
    </div>
  `;

  root.appendChild(overlay);
  root.appendChild(panel);
  root.appendChild(fab);
  document.body.appendChild(root);

  const $list = panel.querySelector(".ikrh-list");
  const $close = panel.querySelector(".ikrh-close");
  const $result = panel.querySelector(".ikrh-result");
  const $toast = panel.querySelector(".ikrh-toast");
  const $btnReset = panel.querySelector('[data-act="reset"]');
  const $btnQuery = panel.querySelector('[data-act="query"]');
  const $overlay = overlay;

  /***********************
   * 渲染
   ***********************/
  function roleByIndex(i, n) {
    if (i === 0) return "起点";
    if (i === n - 1) return "终点";
    return "途经";
  }

  function setToast(type, text) {
    state.toast = { type, text };
    renderToast();
  }

  function clearToast() {
    state.toast = null;
    renderToast();
  }

  function renderToast() {
    if (!state.toast) {
      $toast.style.display = "none";
      $toast.className = "ikrh-toast";
      $toast.textContent = "";
      return;
    }
    $toast.style.display = "block";
    $toast.className = `ikrh-toast ${state.toast.type}`;
    $toast.textContent = state.toast.text;
  }

  function renderResult() {
    if (!state.result) {
      $result.style.display = "none";
      $result.innerHTML = "";
      return;
    }

    const r = state.result;
    $result.style.display = "block";
    $result.innerHTML = `
      <div class="ikrh-result-top">
        <div class="ikrh-metric">
          <div class="k">路程</div>
          <div class="v">${formatDistanceMeters(r.distance)}</div>
        </div>
        <div class="ikrh-metric">
          <div class="k">费用</div>
          <div class="v">${formatMoneyYuan(r.primaryCost)}</div>
        </div>
        <div class="ikrh-metric">
          <div class="k">耗时</div>
          <div class="v">${formatDurationSec(r.duration)}</div>
        </div>
      </div>
    `;
  }

  function buildDropdownHTML(stop) {
    const favorites = stop.showFavorites ? loadFavorites() : [];
    const suggestions = Array.isArray(stop.suggestions) ? stop.suggestions : [];
    const hasFavorites = favorites.length > 0;
    const hasSuggestions = suggestions.length > 0;
    if (!hasFavorites && !hasSuggestions) return "";

    const favGroup = hasFavorites
      ? `
        <div class="ikrh-dd-group">
          <div class="ikrh-dd-group-title">常用地点</div>
          ${favorites.map((fav) => `
            <div class="ikrh-dd-item" data-sug="${encodeURIComponent(JSON.stringify({ name: fav.name, location: fav.location }))}">
              <div class="ikrh-dd-item-content">
                <span class="ikrh-dd-item-name">${escapeHtml(fav.name)}</span>
              </div>
              <button class="ikrh-dd-item-fav favorited" title="取消收藏" data-fav-name="${escapeAttr(fav.name)}" data-fav-loc="${escapeAttr(fav.location)}">★</button>
            </div>
          `).join("")}
        </div>
      `
      : "";

    const sugGroup = hasSuggestions
      ? `
        <div class="ikrh-dd-group">
          <div class="ikrh-dd-group-title">搜索结果</div>
          ${suggestions.map((sug) => `
            <div class="ikrh-dd-item" data-sug="${encodeURIComponent(JSON.stringify({ name: sug.name, location: sug.location }))}">
              <div class="ikrh-dd-item-content">
                <span class="ikrh-dd-item-name">${escapeHtml(sug.name)}</span>
              </div>
              <button class="ikrh-dd-item-fav ${isFavorited(sug.location) ? "favorited" : ""}" title="${isFavorited(sug.location) ? "取消收藏" : "收藏"}" data-fav-name="${escapeAttr(sug.name)}" data-fav-loc="${escapeAttr(sug.location)}">★</button>
            </div>
          `).join("")}
        </div>
      `
      : "";

    return `
      <div class="ikrh-dropdown">
        ${favGroup}
        ${sugGroup}
      </div>
    `;
  }

  function bindDropdownActions(scope) {
    scope.querySelectorAll(".ikrh-dd-item").forEach((item) => {
      item.addEventListener("click", () => {
        const packed = item.getAttribute("data-sug");
        if (!packed) return;

        let obj = null;
        try {
          obj = JSON.parse(decodeURIComponent(packed));
        } catch (e) {
          return;
        }

        const card = item.closest(".ikrh-stop");
        if (!card) return;
        const stopId = card.getAttribute("data-stop-id");
        const s = state.stops.find((x) => x.id === stopId);
        if (!s) return;

        s.text = obj.name || s.text;
        s.location = normalizeLngLat(obj.location) || obj.location || "";
        s.suggestions = [];
        s.showFavorites = false;

        persist();
        clearToast();
        hideAllDropdowns();
        updateDropdowns();
        renderAll();
        bindAllInnerEvents();
        doQuery();
      });
    });

    scope.querySelectorAll(".ikrh-dd-item-fav").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const name = btn.getAttribute("data-fav-name");
        const loc = btn.getAttribute("data-fav-loc");
        if (!loc) return;
        toggleFavorite(name || "", loc);
        updateDropdowns();
      });
    });
  }

  function stopCardTemplate(stop, index, total) {
    const canDelete = total > 2 && index > 0 && index < total - 1;
    const dropdown = buildDropdownHTML(stop);
    return `
      <div class="ikrh-stop" draggable="true" data-stop-id="${stop.id}">
        <div class="ikrh-drag" title="拖拽排序">≡</div>
        <div class="ikrh-stop-num">${index + 1}</div>
        <div class="ikrh-input-wrap">
          <input class="ikrh-input"
            data-input="${stop.id}"
            value="${escapeAttr(stop.text || "")}"
            placeholder="输入地址关键词"
            autocomplete="off"
          />
          ${dropdown}
        </div>
        ${canDelete ? `<button class="ikrh-delete" title="删除途径点" data-delete="${stop.id}">×</button>` : ""}
      </div>
    `;
  }

  // 保存当前聚焦的输入框ID和光标位置
  let focusedInputId = null;
  let focusedInputSelection = null;

  function saveInputFocus() {
    const active = document.activeElement;
    if (active && active.classList.contains("ikrh-input")) {
      focusedInputId = active.getAttribute("data-input");
      focusedInputSelection = { start: active.selectionStart, end: active.selectionEnd };
    } else {
      focusedInputId = null;
      focusedInputSelection = null;
    }
  }

  function restoreInputFocus() {
    if (focusedInputId && focusedInputSelection) {
      const input = $list.querySelector(`[data-input="${focusedInputId}"]`);
      if (input) {
        input.focus();
        if (input.setSelectionRange) {
          input.setSelectionRange(focusedInputSelection.start, focusedInputSelection.end);
        }
      }
    }
  }

  function renderList() {
    saveInputFocus();
    $list.innerHTML = state.stops.map((s, i) => stopCardTemplate(s, i, state.stops.length)).join("") +
      `<div class="ikrh-add-waypoint" data-act="add-waypoint">+ 添加途径点</div>`;
    restoreInputFocus();
  }

  function renderAll() {
    panel.classList.toggle("open", state.open);
    $overlay.classList.toggle("open", state.open);
    renderList();
    renderResult();
    renderToast();
    if ($btnQuery) {
      $btnQuery.textContent = state.querying ? "查询中…" : "查询";
      $btnQuery.disabled = state.querying;
    }
  }

  function openPanel() {
    state.open = true;
    renderAll();
    bindAllInnerEvents();
  }
  function closePanel() {
    state.open = false;
    renderAll();
  }

  /***********************
   * HTML escape（避免注入）
   ***********************/
  function escapeHtml(str) {
    return String(str)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
  function escapeAttr(str) {
    return escapeHtml(str).replaceAll("\n", " ");
  }

  /***********************
   * 交互：拖拽排序
   ***********************/
  let dragId = null;

  function bindDnD() {
    const cards = $list.querySelectorAll(".ikrh-stop");

    cards.forEach((card) => {
      card.addEventListener("dragstart", (e) => {
        dragId = card.getAttribute("data-stop-id");
        card.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
      });

      card.addEventListener("dragend", () => {
        dragId = null;
        cards.forEach((c) => c.classList.remove("dragging", "drop-target"));
      });

      card.addEventListener("dragover", (e) => {
        e.preventDefault();
        const targetId = card.getAttribute("data-stop-id");
        if (!dragId || dragId === targetId) return;
        card.classList.add("drop-target");
      });

      card.addEventListener("dragleave", () => {
        card.classList.remove("drop-target");
      });

      card.addEventListener("drop", (e) => {
        e.preventDefault();
        const targetId = card.getAttribute("data-stop-id");
        if (!dragId || dragId === targetId) return;

        const from = state.stops.findIndex((s) => s.id === dragId);
        const to = state.stops.findIndex((s) => s.id === targetId);
        if (from < 0 || to < 0) return;

        const [moved] = state.stops.splice(from, 1);
        state.stops.splice(to, 0, moved);

        persist();
        renderAll();
        bindAllInnerEvents();
        doQuery();
      });
    });
  }

  /***********************
   * 交互：输入联想 & 下拉选择
   ***********************/
  // 只更新下拉列表，不重新渲染整个列表
  function updateDropdown(stopId) {
    const stop = state.stops.find((s) => s.id === stopId);
    if (!stop) return;

    const card = $list.querySelector(`[data-stop-id="${stopId}"]`);
    if (!card) return;

    const wrap = card.querySelector(".ikrh-input-wrap");
    if (!wrap) return;

    // 移除旧的下拉
    const oldDropdown = wrap.querySelector(".ikrh-dropdown");
    if (oldDropdown) oldDropdown.remove();

    const dropdownHtml = buildDropdownHTML(stop);
    if (dropdownHtml) {
      const container = document.createElement("div");
      container.innerHTML = dropdownHtml;
      const dropdown = container.firstElementChild;
      if (dropdown) {
        wrap.appendChild(dropdown);
        bindDropdownActions(dropdown);
      }
    }
  }

  const debouncedFetch = debounce(async (stopId, value) => {
    const stop = state.stops.find((s) => s.id === stopId);
    if (!stop) return;

    const v = String(value || "").trim();
    if (!v || v.length < 2) {
      stop.suggestions = [];
      stop.loading = false;
      updateDropdown(stopId);
      return;
    }

    // 如果用户直接输入经纬度：直接锁定坐标，不走 geocode
    if (isLngLatLike(v)) {
      const loc = normalizeLngLat(v);
      stop.location = loc || "";
      stop.suggestions = [];
      stop.loading = false;
      persist();
      updateDropdown(stopId);
      return;
    }

    stop.loading = true;
    updateDropdown(stopId);

    try {
      const sug = await searchPlace(v);
      // 如果用户又改了输入，不覆盖新内容（简单版本：校验一致）
      const current = stop.text.trim();
      if (current !== v) return;

      stop.suggestions = sug;
      stop.loading = false;
      updateDropdown(stopId);
    } catch (err) {
      stop.loading = false;
      stop.suggestions = [];
      updateDropdown(stopId);
    }
  }, 350);

  function hideAllDropdowns() {
    state.stops.forEach((s) => {
      s.suggestions = [];
      s.showFavorites = false;
    });
  }

  function bindAllInnerEvents() {
    // 删除途径点按钮
    $list.querySelectorAll("[data-delete]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = btn.getAttribute("data-delete");
        const index = state.stops.findIndex((x) => x.id === id);
        if (index < 0 || index === 0 || index === state.stops.length - 1) return;

        state.stops.splice(index, 1);
        persist();
        clearToast();
        state.result = null;
        renderAll();
        bindAllInnerEvents();
        doQuery();
      });
    });

    // 添加途径点按钮
    const $addWaypoint = $list.querySelector('[data-act="add-waypoint"]');
    if ($addWaypoint) {
      $addWaypoint.replaceWith($addWaypoint.cloneNode(true));
      const newBtn = $list.querySelector('[data-act="add-waypoint"]');
      newBtn.addEventListener("click", () => {
        const newStop = {
          id: uid("stop"),
          text: "",
          location: "",
          suggestions: [],
          loading: false,
        showFavorites: false,
        };
        // 插入到最后一个之前（终点之前）
        state.stops.splice(state.stops.length - 1, 0, newStop);
        persist();
        renderAll();
        bindAllInnerEvents();
      });
    }

    // 清空按钮
    $list.querySelectorAll("[data-clear]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-clear");
        const s = state.stops.find((x) => x.id === id);
        if (!s) return;
        s.text = "";
        s.location = "";
        s.suggestions = [];
        persist();
        clearToast();
        state.result = null;
        renderAll();
        bindAllInnerEvents();
      });
    });

    // 输入框
    $list.querySelectorAll("[data-input]").forEach((inp) => {
      // 移除旧的事件监听器（通过克隆节点）
      const newInp = inp.cloneNode(true);
      inp.parentNode.replaceChild(newInp, inp);

      const handleInputChange = () => {
        const stopId = newInp.getAttribute("data-input");
        const s = state.stops.find((x) => x.id === stopId);
        if (!s) return;

        s.text = newInp.value;
        // 只要用户手动编辑，就先解除 location 锁定（除非输入本身就是经纬度）
        if (!isLngLatLike(newInp.value)) s.location = "";
        s.showFavorites = true;

        clearToast();
        state.result = null;
        updateDropdown(stopId);
        debouncedFetch(stopId, newInp.value);
        persist();
      };

      newInp.addEventListener("compositionstart", () => {
        newInp.dataset.composing = "1";
      });
      newInp.addEventListener("compositionend", () => {
        delete newInp.dataset.composing;
        handleInputChange();
      });
      newInp.addEventListener("input", () => {
        if (newInp.dataset.composing === "1") return;
        handleInputChange();
      });

      newInp.addEventListener("focus", () => {
        // focus 时如果有内容则尝试刷新候选
        const stopId = newInp.getAttribute("data-input");
        const s = state.stops.find((x) => x.id === stopId);
        if (!s) return;
        s.showFavorites = true;
        updateDropdown(stopId);
        if (s.text && s.text.trim().length >= 2 && !s.location && !isLngLatLike(s.text)) {
          debouncedFetch(stopId, s.text);
        }
      });

      newInp.addEventListener("click", () => {
        if (newInp.value) {
          newInp.select();
        }
      });
    });

    // 下拉候选点击
    $list.querySelectorAll(".ikrh-dd-item").forEach((item) => {
      item.addEventListener("click", () => {
        const packed = item.getAttribute("data-sug");
        if (!packed) return;

        let obj = null;
        try {
          obj = JSON.parse(decodeURIComponent(packed));
        } catch (e) {
          return;
        }

        // 找到它属于哪个 stop：向上找卡片
        const card = item.closest(".ikrh-stop");
        if (!card) return;
        const stopId = card.getAttribute("data-stop-id");
        const s = state.stops.find((x) => x.id === stopId);
        if (!s) return;

        s.text = obj.name || s.text;
        s.location = normalizeLngLat(obj.location) || obj.location || "";
        s.suggestions = [];
        s.showFavorites = false;

        persist();
        clearToast();
        hideAllDropdowns();
        updateDropdowns();
        renderAll();
        bindAllInnerEvents();
        doQuery();
      });
    });

    // 点击弹窗内空白不关闭，点击弹窗外关闭下拉
    const clickHandler = (e) => {
      const target = e.target;
      // 点到 input 或 dropdown 不处理
      if (target?.classList?.contains("ikrh-input")) return;
      if (target?.closest?.(".ikrh-dropdown")) return;
      hideAllDropdowns();
      updateDropdowns();
    };

    // 移除旧的事件监听器
    panel.removeEventListener("click", clickHandler);
    panel.addEventListener("click", clickHandler);

    bindDnD();
  }

  function updateDropdowns() {
    state.stops.forEach((stop) => {
      updateDropdown(stop.id);
    });
  }

  /***********************
   * 查询逻辑
   ***********************/
  async function doQuery() {
    clearToast();
    state.result = null;

    // 每次 query 前，确保坐标就绪：允许输入本身是经纬度
    for (const s of state.stops) {
      const t = String(s.text || "").trim();
      if (!s.location && isLngLatLike(t)) {
        s.location = normalizeLngLat(t) || "";
      }
    }

    const seq = state.stops.map((s) => ({
      text: String(s.text || "").trim(),
      location: String(s.location || "").trim(),
    }));

    // 至少起点 & 终点
    const origin = seq[0]?.location;
    const destination = seq[seq.length - 1]?.location;
    const waypoints = seq.slice(1, -1).map((x) => x.location).filter(Boolean);

    if (!origin || !destination) {
      setToast("warn", "请至少选择起点与终点（请在下拉候选中选择或使用常用地点）。");
      renderAll();
      return;
    }

    state.querying = true;
    renderAll();

    try {
      const res = await drivingRoute({ origin, destination, waypoints });
      state.result = res;
      setToast("ok", "查询成功 ✅");
    } catch (err) {
      setToast("err", `查询失败：${err?.message || "未知错误"}`);
    } finally {
      state.querying = false;
      renderAll();
      bindAllInnerEvents();
    }
  }

  /***********************
   * 外层按钮绑定
   ***********************/
  fab.addEventListener("click", () => {
    if (state.open) {
      closePanel();
    } else {
      openPanel();
    }
  });

  $close.addEventListener("click", () => {
    closePanel();
  });

  $overlay.addEventListener("click", () => {
    closePanel();
  });

  $btnReset.addEventListener("click", () => {
    state.stops = defaultStops();
    state.result = null;
    clearToast();
    persist();
    renderAll();
    bindAllInnerEvents();
  });

  // ESC 关闭弹窗
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.open) {
      closePanel();
    }
  });

  // 初次渲染
  renderAll();
  bindAllInnerEvents();

})();
