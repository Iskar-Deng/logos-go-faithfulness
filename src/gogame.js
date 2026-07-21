const Board = require('@sabaki/go-board');

const LETTERS = 'ABCDEFGHJKLMNOPQRST';

class GoGame {
  constructor() {
    this.board = Board.fromDimensions(19);
  }

  move(sign, vertex) {
    try {
      this.board = this.board.makeMove(Number(sign), vertex, {
        preventOverwrite: true,
        preventSuicide: true,
        preventKo: true
      });
      return { success: true, message: '落子成功' };
    } catch (error) {
      return { success: false, message: error.message };
    }
  }

  batchMove(moves) {
    const steps = [];
    let success = true;
    let message = '批量落子完成';

    for (const [index, move] of moves.entries()) {
      const result = this.move(move.sign, move.vertex);
      steps.push({
        step: index + 1,
        sign: move.sign,
        vertex: move.vertex,
        pos: vertexToPos(move.vertex),
        success: result.success,
        message: result.message
      });

      if (!result.success) {
        success = false;
        message = `第${index + 1}步落子失败: ${result.message}`;
        break;
      }
    }

    return {
      success,
      message,
      steps,
      board: this.board.signMap,
      stats: getStats(this.board.signMap)
    };
  }

  batchCheck(moves) {
    let tempBoard = this.board;
    const results = [];

    for (const [index, move] of moves.entries()) {
      try {
        const result = tempBoard.analyzeMove(Number(move.sign), move.vertex);
        const isValid = !result.suicide && !result.ko && !result.overwrite && !result.pass;

        results.push({
          step: index + 1,
          sign: move.sign,
          vertex: move.vertex,
          pos: vertexToPos(move.vertex),
          isValid,
          reason: isValid ? '合法' : invalidReason(result)
        });

        if (!isValid) break;
        tempBoard = tempBoard.makeMove(Number(move.sign), move.vertex, {
          preventOverwrite: true,
          preventSuicide: true,
          preventKo: true
        });
      } catch (error) {
        results.push({
          step: index + 1,
          sign: move.sign,
          vertex: move.vertex,
          pos: vertexToPos(move.vertex),
          isValid: false,
          reason: error.message
        });
        break;
      }
    }

    return results;
  }
}

function quickBatchMove(moves) {
  return new GoGame().batchMove(moves);
}

function quickBatchCheck(moves) {
  return new GoGame().batchCheck(moves);
}

function normalizeMoves(moves) {
  if (!Array.isArray(moves)) throw new Error('moves must be an array');

  return moves.map((move, index) => {
    const pos = String(move.pos || move.move || '').trim().toUpperCase();
    const sign = Number(move.sign || (index % 2 === 0 ? 1 : -1));
    if (sign !== 1 && sign !== -1) throw new Error(`Invalid sign at move ${index + 1}`);

    return {
      sign,
      pos,
      vertex: Array.isArray(move.vertex) ? move.vertex : posToVertex(pos)
    };
  });
}

function posToVertex(pos) {
  const match = /^([A-HJ-T])(\d{1,2})$/.exec(pos);
  if (!match) throw new Error(`Invalid Go coordinate: ${pos}`);

  const x = LETTERS.indexOf(match[1]);
  const number = Number(match[2]);
  if (x < 0 || number < 1 || number > 19) throw new Error(`Invalid Go coordinate: ${pos}`);
  return [x, 19 - number];
}

function vertexToPos(vertex) {
  if (!Array.isArray(vertex) || vertex.length !== 2) return '';
  const [x, y] = vertex;
  if (x < 0 || x >= 19 || y < 0 || y >= 19) return '';
  return `${LETTERS[x]}${19 - y}`;
}

function getStats(board) {
  let black = 0;
  let white = 0;
  let empty = 0;

  for (const row of board) {
    for (const value of row) {
      if (value === 1) black += 1;
      else if (value === -1) white += 1;
      else empty += 1;
    }
  }

  return { black, white, empty };
}

function invalidReason(result) {
  if (result.suicide) return '自杀手';
  if (result.ko) return '劫争';
  if (result.overwrite) return '已有棋子';
  if (result.pass) return '停着';
  return '未知原因';
}

module.exports = {
  GoGame,
  quickBatchMove,
  quickBatchCheck,
  normalizeMoves,
  posToVertex,
  vertexToPos
};
