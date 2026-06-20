/**
 * Generates photo-checklist.md from JSX mock data files.
 * Run: node gen-photo-checklist.js
 */
const fs = require('fs');
const vm = require('vm');

function extractPOIs(src) {
  let ctx = { window: {}, console: console };
  vm.runInNewContext(src, ctx);
  return ctx.window.beijingPOIs || ctx.window.shanghaiPOIs || [];
}

const bjSrc = fs.readFileSync('routeplan/mock-data/beijing-pois.jsx', 'utf8');
const shSrc = fs.readFileSync('routeplan/mock-data/shanghai-pois.jsx', 'utf8');

const beijingPOIs = extractPOIs(bjSrc);
const shanghaiPOIs = extractPOIs(shSrc);

const CAT_LABEL = { 'attraction': '景点', 'food': '美食' };

function photoNum(poi) {
  let parts = poi.id.split('-');
  let num = parseInt(parts[1]);
  if (parts[0] === 'bj') return `photo-${String(num).padStart(3, '0')}`;
  // Shanghai: sh-001~100 → photo-201~300, sh-101~200 → photo-301~400
  if (num <= 100) return `photo-${String(num + 200).padStart(3, '0')}`;
  return `photo-${String(num + 200).padStart(3, '0')}`;
}

function genTable(pois) {
  let lines = [];
  lines.push('| 编号 | POI名称 | 类型 |');
  lines.push('|------|---------|------|');
  for (let p of pois) {
    lines.push(`| ${photoNum(p)} | ${p.name} | ${CAT_LABEL[p.category] || '景点'} |`);
  }
  return lines.join('\n');
}

let output = `# Mock POI 图片清单

## 说明
- 所有图片统一使用 \`images/stores/photo-编号.jpg\` 格式
- 北京POI使用 photo-001 ~ photo-200 (共${beijingPOIs.length}个)
- 上海POI使用 photo-201 ~ photo-400 (共${shanghaiPOIs.length}个)
- 请将图片放入 \`routeplan/images/stores/\` 目录

---

## 北京 (photo-001 ~ photo-200)

${genTable(beijingPOIs)}

---

## 上海 (photo-201 ~ photo-400)

${genTable(shanghaiPOIs)}

---

## 统计

| 城市 | POI数量 | 图片编号范围 |
|------|---------|-------------|
| 北京 | ${beijingPOIs.length}个 | photo-001 ~ photo-200 |
| 上海 | ${shanghaiPOIs.length}个 | photo-201 ~ photo-400 |
| **合计** | **${beijingPOIs.length + shanghaiPOIs.length}个** | **photo-001 ~ photo-400** |

## 图片获取建议

你可以通过以下方式获取这些图片：
1. **运行 download-images.js** - 自动从 Pexels/Pixabay API 下载
2. **百度搜索** - 搜索POI名称，下载合适的图片
3. **大众点评/美团** - 搜索商家，保存店铺图片
4. **Unsplash/Pexels** - 免费图库搜索相关主题

图片建议尺寸：800x600 或 1200x800，格式为 JPG，文件大小控制在 200KB 以内。
`;

fs.writeFileSync('routeplan/mock-data/photo-checklist.md', output, 'utf8');
console.log(`Generated photo-checklist.md with ${beijingPOIs.length} Beijing + ${shanghaiPOIs.length} Shanghai = ${beijingPOIs.length + shanghaiPOIs.length} POIs`);
