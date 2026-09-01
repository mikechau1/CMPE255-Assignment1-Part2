import test from 'node:test';
import assert from 'node:assert/strict';
import {buildNetwork, estimatedBasketGmv, estimatedUnitPrice, isDragGesture, recommendForCart, toGraphPoint} from './networkData.js';

const rules = [{antecedent:['milk'], consequent:['bread'], lift:2, confidence:.7, support:.2, validation_hit_rate:.6}];

test('network contains directed rule endpoints', () => {
  const graph = buildNetwork(rules);
  assert.deepEqual(graph.nodes.map(node => node.id).sort(), ['bread', 'milk']);
  assert.equal(graph.edges[0].source, 'milk');
});

test('cart recommendations require the antecedent', () => {
  assert.equal(recommendForCart(rules, []).length, 0);
  assert.equal(recommendForCart(rules, ['milk'])[0].item, 'bread');
});

test('estimated basket GMV is deterministic and quantity aware', () => {
  const price = estimatedUnitPrice('milk');
  assert.equal(estimatedUnitPrice('milk'), price);
  assert.equal(estimatedBasketGmv({milk: 2}), Number((price * 2).toFixed(2)));
  assert.equal(estimatedBasketGmv({milk: 2}, {milk: 3.5}), 7);
});

test('pointer coordinates map browser pixels into the SVG viewBox', () => {
  assert.deepEqual(toGraphPoint(500, 310, {left:100, top:50, width:400, height:260}, 1), {x:800, y:520});
  assert.deepEqual(toGraphPoint(300, 180, {left:100, top:50, width:400, height:260}, 2), {x:400, y:260});
});

test('drag gesture suppresses click after meaningful movement', () => {
  assert.equal(isDragGesture(10, 10, 12, 12), false);
  assert.equal(isDragGesture(10, 10, 20, 10), true);
});
