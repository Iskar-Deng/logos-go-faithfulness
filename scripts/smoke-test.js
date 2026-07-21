const assert = require('assert');
const { quickBatchMove, normalizeMoves } = require('../src/gogame');

const moves = normalizeMoves([
  { pos: 'Q16' },
  { pos: 'D16' },
  { pos: 'Q4' },
  { pos: 'D4' }
]);

const result = quickBatchMove(moves);
assert.equal(result.success, true);
assert.equal(result.board[3][15], 1);
assert.equal(result.board[3][3], -1);
assert.equal(result.board[15][15], 1);
assert.equal(result.board[15][3], -1);

console.log('smoke test passed');
