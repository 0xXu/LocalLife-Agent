/**
 * POI Image Downloader v4 — Baidu-fallback + Pexels hybrid with global deduplication.
 *
 * Sources (tried in order):
 *   1. Baidu image search scraping (best Chinese POI coverage)
 *   2. Pexels API fallback (when Baidu fails or rate-limited)
 *
 * Key improvements over v3:
 *   - Global URL dedup across ALL POIs (prevents ANY duplicate image)
 *   - Baidu as primary source for Chinese POI coverage
 *   - Larger fallback pools with page-randomization
 *   - Per-image resume (checks each -1, -2, -3, -4 individually)
 *
 * Usage: PEXELS_API_KEY=your_key node download-images.js
 *   --dry-run     Show what would be downloaded
 *   --force       Re-download even if files exist
 *   --city=北京    Only process one city
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { Buffer } = require('buffer');

const OUTPUT_DIR = path.join(__dirname, 'routeplan', 'images', 'stores');
const CHECKLIST_PATH = path.join(__dirname, 'routeplan', 'mock-data', 'photo-checklist.md');
const PEXELS_KEY = process.env.PEXELS_API_KEY || '';
const DELAY_MS = 2000;
const IMAGES_PER_POI = 4;

const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry-run');
const FORCE = args.includes('--force');
const CITY_FILTER = args.find(a => a.startsWith('--city='))?.split('=')[1] || null;

// Global deduplication — never download the same URL twice
let globalUsedUrls = new Set();

// ====================================================================
// POI English name mappings (for Pexels fallback)
// ====================================================================
const POI_EN_NAMES = {
  '故宫博物院': 'Forbidden City Beijing China',
  '八达岭长城': 'Great Wall of China Badaling',
  '天坛公园': 'Temple of Heaven Beijing China',
  '颐和园': 'Summer Palace Beijing China',
  '圆明园遗址公园': 'Old Summer Palace Beijing China',
  '北海公园': 'Beihai Park Beijing China',
  '雍和宫': 'Yonghe Temple Lama Temple Beijing',
  '恭王府': 'Prince Gong Mansion Beijing',
  '国家体育场(鸟巢)': 'Bird Nest Stadium Beijing China',
  '国家游泳中心(水立方)': 'Water Cube Beijing China',
  '中央电视台总部大楼': 'CCTV Headquarters Beijing China',
  '北京环球度假区': 'Universal Studios Beijing China',
  '北京欢乐谷': 'Happy Valley Beijing amusement park',
  '三里屯太古里': 'Taikoo Li Sanlitun Beijing',
  '王府井大街': 'Wangfujing Street Beijing China',
  '中国国家博物馆': 'National Museum of China Beijing',
  '香山公园': 'Fragrant Hills Beijing China',
  '慕田峪长城': 'Mutianyu Great Wall Beijing China',
  '南锣鼓巷': 'Nanluoguxiang Hutong Beijing China',
  '什刹海': 'Shichahai Houhai Beijing China',
  '古北水镇': 'Gubei Water Town Beijing China',
  '清华大学': 'Tsinghua University Beijing China',
  '北京大学': 'Peking University Beijing China',
  '外滩': 'The Bund Shanghai China skyline',
  '东方明珠广播电视塔': 'Oriental Pearl Tower Shanghai China',
  '上海迪士尼乐园': 'Shanghai Disneyland China',
  '豫园': 'Yu Garden Shanghai China',
  '南京路步行街': 'Nanjing Road Shanghai China',
  '上海中心大厦': 'Shanghai Tower China',
  '田子坊': 'Tianzifang Shanghai China old street',
  '新天地': 'Xintiandi Shanghai China',
  '陆家嘴金融区': 'Lujiazui Pudong Shanghai skyline',
  '中华艺术宫': 'China Art Palace Shanghai Expo',
  '武康路': 'Wukang Road Shanghai Ferguson Lane',
  '上海动物园': 'Shanghai Zoo China',
  '世纪公园': 'Century Park Shanghai China',
  '外滩源': 'Rockbund Shanghai China',
  '复旦大学': 'Fudan University Shanghai China',
  // New SHOPPING / CULTURE POIs
  'PageOne书店(三里屯店)': 'PageOne bookstore Sanlitun Beijing',
  '红砖美术馆': 'Red Brick Art Museum Beijing China',
  '798艺术区·UCCA': 'UCCA Center for Contemporary Art Beijing 798',
  '言几又·今日阅读(国贸店)': 'Yan Ji You bookstore Beijing China',
  '三里屯太古里买手店街': 'Taikoo Li Sanlitun boutique shopping Beijing',
  '衡山·和集': 'Hengshan bookshop Shanghai China',
  '西岸美术馆': 'West Bund Museum Shanghai China',
  '香蕉鱼书店': 'Banana Fish bookstore Shanghai China',
  '安福路买手店街': 'Anfu Road boutique stores Shanghai China',
  '老场坊1933': '1933 Old Millfun Shanghai creative space',
};

// Diverse category-based queries — cycled through to maximize uniqueness
const CATEGORY_QUERIES = {
  '北京': {
    'ATTRACTION': [
      'Beijing China temple', 'Beijing historic site', 'Beijing palace China',
      'Beijing garden park', 'Beijing landmark', 'Beijing ancient architecture',
      'Beijing imperial palace', 'Beijing traditional garden', 'Beijing city wall',
      'Beijing old street', 'Beijing hutongs', 'Beijing lakes park',
      'Beijing spring temple', 'Beijing autumn leaves', 'Beijing mountain view',
    ],
    'RESTAURANT': [
      'Beijing roast duck restaurant', 'Chinese food Beijing dining',
      'Beijing cuisine hotpot', 'Beijing noodles', 'Beijing traditional food',
      'Beijing restaurant interior', 'Chinese dumplings Beijing',
      'Beijing street food', 'Beijing upscale dining', 'Beijing tea house',
      'Beijing local cuisine', 'Beijing seafood', 'Beijing hot pot',
      'Beijing fine dining', 'Beijing dim sum',
    ],
    'SHOPPING': [
      'Beijing bookstore interior', 'Beijing boutique shopping',
      'Beijing fashion store', 'Beijing designer shop',
      'Beijing concept store', 'Beijing trendy shopping street',
      'Beijing mall interior', 'Beijing retail store',
    ],
    'CULTURE': [
      'Beijing art museum', 'Beijing contemporary art',
      'Beijing gallery space', 'Beijing creative district',
      'Beijing exhibition hall', 'Beijing cultural venue',
      'Beijing architecture art', 'Beijing art center',
    ],
  },
  '上海': {
    'ATTRACTION': [
      'Shanghai China skyline', 'Shanghai bund view', 'Shanghai landmark building',
      'Shanghai garden China', 'Shanghai old street architecture',
      'Shanghai river view', 'Shanghai modern architecture', 'Shanghai park',
      'Shanghai traditional garden', 'Shanghai temple', 'Shanghai waterfront',
      'Shanghai night view', 'Shanghai cityscape pudong',
    ],
    'RESTAURANT': [
      'Shanghai cuisine food', 'Shanghai restaurant dining',
      'Shanghai xiaolongbao', 'Shanghai street food', 'Shanghai fine dining',
      'Shanghai seafood', 'Shanghai noodles', 'Shanghai traditional food',
      'Shanghai upscale restaurant', 'Shanghai cafe', 'Shanghai dim sum',
      'Shanghai hot pot', 'Shanghai local food', 'Shanghai brunch',
    ],
    'SHOPPING': [
      'Shanghai bookstore interior', 'Shanghai boutique store',
      'Shanghai fashion shopping', 'Shanghai designer store',
      'Shanghai concept store', 'Shanghai vintage shop',
      'Shanghai shopping street', 'Shanghai mall interior',
    ],
    'CULTURE': [
      'Shanghai art museum', 'Shanghai contemporary art gallery',
      'Shanghai creative space', 'Shanghai cultural center',
      'Shanghai exhibition hall', 'Shanghai art district',
      'Shanghai architecture interior', 'Shanghai gallery space',
    ],
  }
};

// ====================================================================
// Baidu Image Search (primary source for Chinese POIs)
// ====================================================================

let baiduCookies = null;

async function getBaiduCookies() {
  if (baiduCookies) return baiduCookies;
  return new Promise((resolve) => {
    const req = https.get('https://image.baidu.com/', {
      headers: {
        'User-Agent': BROWSER_UA,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      },
      timeout: 10000,
    }, (res) => {
      const cookies = (res.headers['set-cookie'] || []).map(c => c.split(';')[0]).join('; ');
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        baiduCookies = cookies;
        resolve(cookies);
      });
    });
    req.on('error', () => resolve(''));
    req.on('timeout', () => { req.destroy(); resolve(''); });
  });
}

// CDN domains that are known to hotlink-block — skip them
const BLOCKED_CDNS = [
  'douyinpic.com', 'douyincdn.com', 'douyin.com',
];

function isBlockedUrl(url) {
  try {
    const host = new URL(url).hostname;
    // Skip webp URLs — frontend expects consistent extensions per POI
    const ext = new URL(url).pathname.split('.').pop().toLowerCase();
    if (ext === 'webp') return true;
    return BLOCKED_CDNS.some(d => host.includes(d));
  } catch { return true; }
}

async function searchBaidu(query, count = 30) {
  for (let attempt = 1; attempt <= 2; attempt++) {
    try {
      const cookies = await getBaiduCookies();
      const encoded = encodeURIComponent(query);
      const searchUrl = `https://image.baidu.com/search/flip?tn=baiduimage&word=${encoded}&pn=0&rn=${Math.min(count, 20)}`;

      const html = await new Promise((resolve, reject) => {
        https.get(searchUrl, {
          headers: {
            'User-Agent': BROWSER_UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://image.baidu.com/',
            'Cookie': cookies,
          },
          timeout: 15000,
        }, (res) => {
          if (res.statusCode !== 200) {
            res.resume();
            return reject(new Error(`HTTP ${res.statusCode}`));
          }
          let body = '';
          res.on('data', c => body += c);
          res.on('end', () => resolve(body));
          res.on('error', reject);
        }).on('error', reject).on('timeout', function() { this.destroy(); reject(new Error('timeout')); });
      });

      const urls = [];
      const seenUrls = new Set();

      // Strategy 1: thumbURL (Baidu's own CDN — most reliable, no hotlink issues)
      const thumbPattern = /"thumbURL"\s*:\s*"(https?:\/\/[^"]+)"/g;
      let match;
      while ((match = thumbPattern.exec(html)) !== null) {
        let url = match[1].split('\\/').join('/');
        if (url && !seenUrls.has(url) && !globalUsedUrls.has(url)) {
          seenUrls.add(url);
          urls.push({ url, source: 'baidu' });
        }
      }

      // Strategy 2: middleURL (Baidu CDN medium size)
      const midPattern = /"middleURL"\s*:\s*"(https?:\/\/[^"]+)"/g;
      while ((match = midPattern.exec(html)) !== null) {
        let url = match[1].split('\\/').join('/');
        if (url && !seenUrls.has(url) && !globalUsedUrls.has(url)) {
          seenUrls.add(url);
          urls.push({ url, source: 'baidu' });
        }
      }

      // Strategy 3: objURL from non-blocked domains
      const objUrlPattern = /"objURL"\s*:\s*"(https?:\/\/[^"]+)"/g;
      while ((match = objUrlPattern.exec(html)) !== null) {
        let url = match[1].split('\\/').join('/');
        if (url && !isBlockedUrl(url) && !seenUrls.has(url) && !globalUsedUrls.has(url)) {
          seenUrls.add(url);
          urls.push({ url, source: 'baidu' });
        }
      }

      return urls;
    } catch (e) {
      if (attempt === 2) return [];
      baiduCookies = null;
      await sleep(1000);
    }
  }
  return [];
}

// ====================================================================
// Pexels (fallback source)
// ====================================================================

const BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

function httpGet(url, headers = {}, binary = false, referer = null) {
  return new Promise((resolve, reject) => {
    const proto = url.startsWith('https') ? https : http;
    const reqHeaders = {
      'User-Agent': BROWSER_UA,
      'Accept': binary ? 'image/webp,image/*,*/*;q=0.8' : 'application/json,text/html,*/*',
      'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      ...headers,
    };
    if (referer) reqHeaders['Referer'] = referer;
    const req = proto.get(url, { headers: reqHeaders, timeout: 25000 }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return httpGet(res.headers.location, headers, binary, referer).then(resolve).catch(reject);
      }
      if (res.statusCode === 429) { res.resume(); return reject(new Error('RATE_LIMIT')); }
      if (res.statusCode !== 200) { res.resume(); return reject(new Error(`HTTP ${res.statusCode}`)); }
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve(binary ? Buffer.concat(chunks) : Buffer.concat(chunks).toString('utf8')));
      res.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

async function searchPexels(query, perPage = 15, page = 1) {
  if (!PEXELS_KEY) return [];
  try {
    const url = `https://api.pexels.com/v1/search?query=${encodeURIComponent(query)}&per_page=${perPage}&orientation=landscape&size=medium&locale=en-US&page=${page}`;
    const raw = await httpGet(url, { Authorization: PEXELS_KEY });
    const data = JSON.parse(raw);
    return (data.photos || []).map(p => ({
      url: p.src?.landscape || p.src?.large || p.src?.original,
      source: 'pexels',
    }));
  } catch (e) {
    if (e.message === 'RATE_LIMIT') throw e;
    return [];
  }
}

function getExt(url) {
  // Extract file extension, default to .jpg
  try {
    const pathname = new URL(url).pathname;
    const m = pathname.match(/\.(jpg|jpeg|png|webp|gif|bmp)(\?|$)/i);
    return m ? m[1].toLowerCase() : 'jpg';
  } catch { return 'jpg'; }
}

async function downloadFile(filepath, url, source = 'baidu') {
  try {
    const referer = source === 'baidu' ? 'https://image.baidu.com/' : null;
    const data = await httpGet(url, {}, true, referer);
    if (data.length < 1024) return { ok: false, error: 'Too small' };
    fs.writeFileSync(filepath, data);
    globalUsedUrls.add(url);
    return { ok: true, kb: (data.length / 1024).toFixed(1) };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

function fileExists(photoId, idx) {
  return fs.existsSync(path.join(OUTPUT_DIR, `${photoId}-${idx}.jpg`));
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ====================================================================
// Smart POI image search with global dedup
// ====================================================================

// Track which generic query indices we've used per city+category to cycle through
const queryIndex = {};

function getNextQueries(city, category, count) {
  const queries = CATEGORY_QUERIES[city]?.[category] || [`${city} China`];
  if (!queryIndex[`${city}_${category}`]) queryIndex[`${city}_${category}`] = 0;
  const start = queryIndex[`${city}_${category}`];
  const result = [];
  for (let i = 0; i < count; i++) {
    result.push(queries[(start + i) % queries.length]);
  }
  queryIndex[`${city}_${category}`] = (start + count) % queries.length;
  return result;
}

async function findImagesForPOI(poi, count) {
  let photos = [];

  // === Strategy 1: Baidu image search (best for Chinese POIs) ===
  try {
    let baiduResults = await searchBaidu(poi.name, count * 8);
    // Filter already-used URLs
    baiduResults = baiduResults.filter(p => !globalUsedUrls.has(p.url));
    photos.push(...baiduResults);
  } catch (e) {
    // Baidu failed silently, continue to Pexels
  }

  // === Strategy 2: Pexels English name mapping ===
  if (photos.length < count) {
    const enName = POI_EN_NAMES[poi.name];
    if (enName) {
      try {
        let results = await searchPexels(enName, count + 5);
        results = results.filter(p => !globalUsedUrls.has(p.url));
        photos.push(...results);
      } catch (e) {
        if (e.message === 'RATE_LIMIT') throw e;
      }
    }
  }

  // === Strategy 3: Pexels Chinese name + city ===
  if (photos.length < count) {
    try {
      let results = await searchPexels(`${poi.name} ${poi.city}`, count + 5);
      results = results.filter(p => !globalUsedUrls.has(p.url));
      for (let p of results) {
        if (!photos.find(ep => ep.url === p.url)) photos.push(p);
      }
    } catch (e) {
      if (e.message === 'RATE_LIMIT') throw e;
    }
  }

  // === Strategy 4: Pexels cleaned name ===
  if (photos.length < count) {
    let cleanName = poi.name.replace(/[()（）].*?[()（）]/g, '').replace(/\(.*$/, '').trim();
    if (cleanName !== poi.name) {
      try {
        let results = await searchPexels(`${cleanName} ${poi.city}`, count + 5);
        results = results.filter(p => !globalUsedUrls.has(p.url));
        for (let p of results) {
          if (!photos.find(ep => ep.url === p.url)) photos.push(p);
        }
      } catch (e) {
        if (e.message === 'RATE_LIMIT') throw e;
      }
    }
  }

  // === Strategy 5: Diverse generic queries with page randomization ===
  if (photos.length < count) {
    const needed = count - photos.length;
    const queries = getNextQueries(poi.city, poi.category, Math.min(needed + 2, 5));
    const pages = queries.map((_, i) => 1 + Math.floor(i * 1.7 + (poi.photoId.charCodeAt(6) || 0) % 3));

    for (let i = 0; i < queries.length && photos.length < count; i++) {
      try {
        let results = await searchPexels(queries[i], 15, pages[i]);
        results = results.filter(p => !globalUsedUrls.has(p.url));
        for (let p of results) {
          if (!photos.find(ep => ep.url === p.url) && photos.length < count) {
            photos.push(p);
          }
        }
        if (i < queries.length - 1) await sleep(300);
      } catch (e) {
        if (e.message === 'RATE_LIMIT') throw e;
      }
    }
  }

  return photos.slice(0, count);
}

// ====================================================================
// Checklist parser
// ====================================================================

function parseChecklist(content) {
  const pois = [];
  let currentCity = '';
  for (let line of content.split('\n')) {
    if (line.includes('## 北京')) currentCity = '北京';
    else if (line.includes('## 上海')) currentCity = '上海';
    else if (line.startsWith('---')) currentCity = '';
    let m = line.match(/^\|\s*(photo-\d+)\s*\|\s*(.+?)\s*\|\s*(\S+?)\s*\|$/);
    if (m) pois.push({
      photoId: m[1],
      name: m[2].trim(),
      category: m[3] === '美食' ? 'RESTAURANT'
              : m[3] === '景点' ? 'ATTRACTION'
              : m[3] === 'CULTURE' ? 'CULTURE'
              : m[3],
      city: currentCity,
    });
  }
  return pois;
}

// ====================================================================
// MAIN
// ====================================================================

async function main() {
  console.log('=== POI Image Downloader v4 (Baidu + Pexels, global dedup) ===\n');

  if (!fs.existsSync(CHECKLIST_PATH)) {
    console.error('Checklist not found. Run: node gen-photo-checklist.js');
    process.exit(1);
  }

  let pois = parseChecklist(fs.readFileSync(CHECKLIST_PATH, 'utf8'));
  console.log(`Found ${pois.length} POIs.`);
  if (CITY_FILTER) { pois = pois.filter(p => p.city === CITY_FILTER); console.log(`Filter: ${CITY_FILTER} → ${pois.length}.`); }

  // Build work list (per-image resume)
  let missingPOIs = [];
  let existingCount = 0;
  for (let poi of pois) {
    let missing = [];
    for (let i = 1; i <= IMAGES_PER_POI; i++) {
      if (!FORCE && fileExists(poi.photoId, i)) { existingCount++; }
      else missing.push(i);
    }
    if (missing.length > 0) missingPOIs.push({ poi, missing });
  }

  let totalSlots = pois.length * IMAGES_PER_POI;
  console.log(`Total: ${totalSlots} slots | Existing: ${existingCount} | Need: ${totalSlots - existingCount}`);
  console.log(`POIs to process: ${missingPOIs.length} (~${Math.ceil(missingPOIs.length * DELAY_MS / 60000)} min)\n`);

  if (!PEXELS_KEY) console.log('⚠ PEXELS_API_KEY not set — using Baidu-only mode.\n');

  if (DRY_RUN) {
    console.log('=== DRY RUN ===');
    for (let { poi, missing } of missingPOIs.slice(0, 20)) {
      console.log(`  ${poi.photoId}: "${poi.name}" missing[${missing.join(',')}]`);
    }
    return;
  }

  if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  let downloaded = 0, skipped = 0;
  let consecutiveBaiduFails = 0;

  for (let idx = 0; idx < missingPOIs.length; idx++) {
    const { poi, missing } = missingPOIs[idx];
    process.stdout.write(`[${idx+1}/${missingPOIs.length}] ${poi.photoId} "${poi.name}" ... `);

    try {
      let photos = await findImagesForPOI(poi, missing.length);

      // Track Baidu health
      if (photos.length === 0 || photos.every(p => p.source === 'pexels')) {
        consecutiveBaiduFails++;
      } else {
        consecutiveBaiduFails = 0;
      }

      if (photos.length === 0) {
        console.log('NO_MATCH');
        skipped += missing.length;
      } else {
        let ok = 0;
        for (let i = 0; i < Math.min(photos.length, missing.length); i++) {
          let filepath = path.join(OUTPUT_DIR, `${poi.photoId}-${missing[i]}.jpg`);
          let r = await downloadFile(filepath, photos[i].url, photos[i].source);
          if (r.ok) { downloaded++; ok++; }
        }
        const src = photos[0]?.source || '?';
        if (ok > 0) {
          console.log(`${ok} OK [${src}]${ok < missing.length ? ` (${missing.length - ok} failed)` : ''}`);
          skipped += (missing.length - ok);
        } else {
          console.log('FAIL');
          skipped += missing.length;
        }
      }
    } catch (e) {
      if (e.message === 'RATE_LIMIT') {
        console.log('RATE_LIMIT — waiting 60s...');
        await sleep(60000);
        idx--; continue;
      }
      console.log(`ERROR: ${e.message}`);
      skipped += missing.length;
    }

    if (idx < missingPOIs.length - 1) await sleep(DELAY_MS);
  }

  let finalCount = pois.reduce((s, p) => {
    for (let i = 1; i <= IMAGES_PER_POI; i++) if (fileExists(p.photoId, i)) s++;
    return s;
  }, 0);
  console.log(`\n=== DONE: ${finalCount}/${totalSlots} images ===`);
  console.log(`Unique URLs tracked: ${globalUsedUrls.size}`);
  if (finalCount < totalSlots) console.log('Re-run to retry missing ones (existing images are skipped).');
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
