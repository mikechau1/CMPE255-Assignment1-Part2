import React, {useMemo, useRef, useState} from 'react';
import {buildNetwork, estimatedBasketGmv, estimatedUnitPrice, isDragGesture, recommendForCart, toGraphPoint} from './networkData.js';

const fmt = (value, digits = 2) => Number(value ?? 0).toFixed(digits);

export default function NetworkCart({rules, priceData = {catalog: {}, pricing: {source: 'unavailable'}}}) {
  const graph = useMemo(() => buildNetwork(rules), [rules]);
  const [positions, setPositions] = useState({});
  const [cart, setCart] = useState({});
  const [query, setQuery] = useState('');
  const [zoom, setZoom] = useState(1);
  const [hovered, setHovered] = useState(null);
  const drag = useRef(null);
  const suppressClick = useRef(false);
  const nodes = graph.nodes.map(node => ({...node, ...(positions[node.id] || {})}));
  const byId = new Map(nodes.map(node => [node.id, node]));
  const cartItems = Object.keys(cart);
  const unitCount = Object.values(cart).reduce((total, quantity) => total + quantity, 0);
  const catalog = priceData.catalog || {};
  const pricing = priceData.pricing || {};
  const observedPrices = pricing.source === 'observed';
  const currency = pricing.currency === 'GBP' ? '£' : '$';
  const basketGmv = estimatedBasketGmv(cart, catalog);
  const recommendations = recommendForCart(rules, cartItems);
  const recommendedItems = new Set(recommendations.map(value => value.item));
  const allItems = [...new Set(rules.flatMap(rule => [...rule.antecedent, ...rule.consequent]))].sort();
  const suggestions = query ? allItems.filter(item => item.includes(query.toLowerCase()) && !cartItems.includes(item)).slice(0, 6) : [];

  const add = item => { setCart(current => ({...current, [item]: (current[item] || 0) + 1})); setQuery(''); };
  const changeQuantity = (item, delta) => setCart(current => {
    const quantity = (current[item] || 0) + delta;
    if (quantity <= 0) { const next = {...current}; delete next[item]; return next; }
    return {...current, [item]: quantity};
  });
  const pointerMove = event => {
    if (!drag.current) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const point = toGraphPoint(event.clientX, event.clientY, rect, zoom);
    drag.current.moved ||= isDragGesture(drag.current.startX, drag.current.startY, event.clientX, event.clientY);
    setPositions(current => ({...current, [drag.current.id]: point}));
  };
  const pointerUp = () => { suppressClick.current = Boolean(drag.current?.moved); drag.current = null; };

  return <section className="network-workspace">
    <div className="panel network-panel">
      <div className="panel-head"><div><p className="eyebrow">2D ASSOCIATION MAP</p><h2>Click a product to add it</h2></div><div className="network-controls"><button onClick={() => setZoom(value => Math.max(.6, value - .15))}>−</button><span>{Math.round(zoom * 100)}%</span><button onClick={() => setZoom(value => Math.min(1.8, value + .15))}>+</button><button onClick={() => {setZoom(1); setPositions({});}}>Reset</button></div></div>
      <div className="network-legend"><span><i className="legend-node cart-node"/> In cart</span><span><i className="legend-node rec-node"/> Recommended</span><span>Width = confidence</span><span>Color = lift</span></div>
      <svg className="association-network" viewBox="0 0 800 520" role="img" aria-label="Interactive directed association-rule network" onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerLeave={pointerUp} onWheel={event => {event.preventDefault(); setZoom(value => Math.max(.6, Math.min(1.8, value + (event.deltaY < 0 ? .1 : -.1))))}}>
        <defs>
          <filter id="nodeGlow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          <radialGradient id="defaultNode"><stop offset="0" stopColor="#ffffff"/><stop offset="1" stopColor="#b9d1d8"/></radialGradient>
          <radialGradient id="recommendedNode"><stop offset="0" stopColor="#efffb8"/><stop offset="1" stopColor="#b8de48"/></radialGradient>
          <radialGradient id="cartNode"><stop offset="0" stopColor="#315565"/><stop offset="1" stopColor="#10222d"/></radialGradient>
          <marker id="arrowHead" markerWidth="8" markerHeight="8" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#89a4ae"/></marker>
        </defs>
        <g transform={`translate(400 260) scale(${zoom}) translate(-400 -260)`}>
          {graph.edges.map((edge, index) => { const source = byId.get(edge.source), target = byId.get(edge.target); if (!source || !target) return null; const active = cartItems.includes(edge.source) || cartItems.includes(edge.target); const dx = target.x - source.x, dy = target.y - source.y, length = Math.max(Math.hypot(dx, dy), 1), bend = (index % 2 ? 1 : -1) * Math.min(18, length * .08), mx = (source.x + target.x) / 2 - dy / length * bend, my = (source.y + target.y) / 2 + dx / length * bend; return <path className="network-edge" key={`${edge.source}-${edge.target}-${index}`} d={`M ${source.x} ${source.y} Q ${mx} ${my} ${target.x} ${target.y}`} fill="none" stroke={active ? '#ff9860' : edge.lift >= 1.5 ? '#b9df52' : '#6f929e'} strokeWidth={Math.max(1, edge.confidence * 4)} opacity={active ? .95 : .48} markerEnd="url(#arrowHead)"/>; })}
          {nodes.map(node => { const selected = cartItems.includes(node.id), recommended = recommendedItems.has(node.id), radius = 13, labelWidth = Math.max(48, node.id.length * 6 + 14); return <g key={node.id} transform={`translate(${node.x} ${node.y})`} className={`network-node ${selected ? 'is-selected' : recommended ? 'is-recommended' : ''}`} onPointerDown={event => {event.currentTarget.setPointerCapture(event.pointerId); drag.current = {id:node.id, startX:event.clientX, startY:event.clientY, moved:false}}} onPointerEnter={() => setHovered(node)} onPointerLeave={() => setHovered(null)} onClick={() => {if (suppressClick.current) {suppressClick.current = false; return;} add(node.id)}} role="button" tabIndex="0" aria-label={`Add ${node.id} to cart`} onKeyDown={event => {if (event.key === 'Enter') add(node.id)}}><circle className="node-halo" r={radius + 8}/><circle className="node-core" r={radius} fill={selected ? 'url(#cartNode)' : recommended ? 'url(#recommendedNode)' : 'url(#defaultNode)'}/><circle className="node-highlight" r={radius - 4}/><rect className="node-label-bg" x={-labelWidth/2} y="22" width={labelWidth} height="17" rx="8.5"/><text y="34" textAnchor="middle">{node.id}</text></g>; })}
        </g>
      </svg>
      {hovered && <div className="network-tooltip"><b>{hovered.id}</b><span>Network strength {fmt(hovered.strength)}</span><span>Click to add · drag to move</span></div>}
    </div>
    <div className="panel cart-panel">
      <div className="cart-title-row"><div><p className="eyebrow">INTERACTIVE SHOPPING BASKET</p><h2>Build a basket</h2></div><div className="gmv-card"><span>{observedPrices ? 'Current basket GMV' : 'Estimated basket GMV'}</span><strong>{currency}{fmt(basketGmv)}</strong><small>{observedPrices ? 'Median observed unit prices' : 'Demo fallback prices'}</small></div></div>
      <p className="cart-help">Add products, adjust quantities, and watch GMV and association-based recommendations update immediately.</p>
      <div className="item-search"><input value={query} onChange={event => setQuery(event.target.value.toLowerCase())} placeholder="Search products..." aria-label="Search products"/>{suggestions.length > 0 && <div className="suggestions">{suggestions.map(item => <button key={item} onClick={() => add(item)}>{item}<span>+</span></button>)}</div>}</div>
      <div className="cart-items"><div className="cart-heading"><span>{cartItems.length} products · {unitCount} units</span>{cartItems.length > 0 && <button onClick={() => setCart({})}>Clear basket</button>}</div>{cartItems.length === 0 ? <div className="empty-cart"><b>Your basket is empty</b><span>Choose an item from the network or search to begin.</span></div> : cartItems.map(item => <div className="cart-item" key={item}><div className="cart-product"><b>{item}</b><span>{currency}{fmt(estimatedUnitPrice(item, catalog))} each</span></div><div className="quantity-control"><button aria-label={`Decrease ${item}`} onClick={() => changeQuantity(item, -1)}>−</button><strong>{cart[item]}</strong><button aria-label={`Increase ${item}`} onClick={() => changeQuantity(item, 1)}>+</button></div><strong className="line-total">{currency}{fmt(estimatedUnitPrice(item, catalog) * cart[item])}</strong><button className="remove-item" aria-label={`Remove ${item}`} onClick={() => changeQuantity(item, -cart[item])}>×</button></div>)}</div>
      <div className="recommendations"><p className="eyebrow">NEXT-BEST ITEMS</p>{recommendations.length === 0 ? <p className="no-recs">Add more products to activate a matching association rule.</p> : recommendations.map(({item, score, rule}) => <button className="recommendation" key={item} onClick={() => add(item)}><div><b>{item}</b><span>{currency}{fmt(estimatedUnitPrice(item, catalog))} · Lift {fmt(rule.lift)} · Confidence {fmt(rule.confidence * 100, 0)}%</span></div><strong>+ Add</strong><i style={{width: `${Math.min(score / 3 * 100, 100)}%`}}/></button>)}</div>
      <p className="gmv-disclaimer">{observedPrices ? 'GMV uses median positive UnitPrice observations from cleaned Kaggle/UCI invoice lines; cancellations and returns are excluded.' : 'Demo fallback prices are active. Add the Online Retail CSV to data/raw and rerun the experiment for observed-price GMV.'}</p>
    </div>
  </section>;
}
