export function buildNetwork(rules, limit = 24) {
  const edgeMap = new Map();
  for (const rule of rules) {
    for (const source of rule.antecedent) {
      for (const target of rule.consequent) {
        if (source === target) continue;
        const key = `${source}\u0000${target}`;
        const existing = edgeMap.get(key);
        if (!existing || rule.lift * rule.confidence > existing.lift * existing.confidence) {
          edgeMap.set(key, {source, target, lift: rule.lift, confidence: rule.confidence, support: rule.support});
        }
      }
    }
  }
  const strength = new Map();
  for (const edge of edgeMap.values()) {
    strength.set(edge.source, (strength.get(edge.source) || 0) + edge.lift * edge.confidence);
    strength.set(edge.target, (strength.get(edge.target) || 0) + edge.lift * edge.confidence);
  }
  const selected = [...strength].sort((a, b) => b[1] - a[1]).slice(0, limit).map(([item]) => item);
  const selectedSet = new Set(selected);
  const nodes = selected.map((id, index) => ({
    id,
    strength: strength.get(id),
    x: 400 + Math.cos(index / selected.length * Math.PI * 2) * (145 + (index % 3) * 25),
    y: 260 + Math.sin(index / selected.length * Math.PI * 2) * (145 + (index % 3) * 25),
  }));
  const edges = [...edgeMap.values()].filter(edge => selectedSet.has(edge.source) && selectedSet.has(edge.target));
  return {nodes, edges};
}

export function recommendForCart(rules, cart, limit = 8) {
  const cartSet = new Set(cart);
  const recommendations = new Map();
  for (const rule of rules) {
    if (!rule.antecedent.every(item => cartSet.has(item))) continue;
    for (const item of rule.consequent) {
      if (cartSet.has(item)) continue;
      const score = rule.lift * rule.confidence * (0.5 + rule.validation_hit_rate);
      const current = recommendations.get(item);
      if (!current || score > current.score) recommendations.set(item, {item, score, rule});
    }
  }
  return [...recommendations.values()].sort((a, b) => b.score - a.score).slice(0, limit);
}

export function estimatedUnitPrice(item, catalog = {}) {
  if (Number.isFinite(Number(catalog[item])) && Number(catalog[item]) > 0) return Number(catalog[item]);
  const hash = [...item].reduce((value, character) => (value * 31 + character.charCodeAt(0)) >>> 0, 7);
  return Number((1.49 + (hash % 1350) / 100).toFixed(2));
}

export function estimatedBasketGmv(lines, catalog = {}) {
  return Number(Object.entries(lines).reduce((total, [item, quantity]) => total + estimatedUnitPrice(item, catalog) * quantity, 0).toFixed(2));
}

export function toGraphPoint(clientX, clientY, rect, zoom, viewWidth = 800, viewHeight = 520) {
  const viewX = (clientX - rect.left) * viewWidth / rect.width;
  const viewY = (clientY - rect.top) * viewHeight / rect.height;
  const centerX = viewWidth / 2;
  const centerY = viewHeight / 2;
  return {
    x: centerX + (viewX - centerX) / zoom,
    y: centerY + (viewY - centerY) / zoom,
  };
}

export function isDragGesture(startX, startY, clientX, clientY, threshold = 5) {
  return Math.hypot(clientX - startX, clientY - startY) > threshold;
}
