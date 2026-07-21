const LETTERS = 'ABCDEFGHJKLMNOPQRST'.split('');
const boardEl = document.querySelector('#board');
const coordTop = document.querySelector('#coordTop');
const coordBottom = document.querySelector('#coordBottom');
const coordLeft = document.querySelector('#coordLeft');
const coordRight = document.querySelector('#coordRight');
const sampleSelect = document.querySelector('#sampleSelect');
const branchSelect = document.querySelector('#branchSelect');
const sampleStatus = document.querySelector('#sampleStatus');
const branchStatus = document.querySelector('#branchStatus');
const branchMoves = document.querySelector('#branchMoves');
const answerBox = document.querySelector('#answerBox');
const sourceTitle = document.querySelector('#sourceTitle');
const sourceBox = document.querySelector('#sourceBox');
const reasoningViewBtn = document.querySelector('#reasoningViewBtn');
const inputViewBtn = document.querySelector('#inputViewBtn');
const note = document.querySelector('#engineNote');

let dataset = [];
let activeSample = null;
let activeBranches = [];
let activeBranch = null;
let stepIndex = 0;
let dataUrl = '/data/logos_rollout_1k_all.tree.json';
let activeTextView = 'reasoning';

init();

async function init() {
  renderCoordinates();
  renderBoard();
  bindEvents();

  try {
    dataUrl = getDataUrl();
    const response = await fetch(dataUrl);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    dataset = await response.json();
    populateSamples();
    selectSample(getSampleId(dataset[0]));
    setNote(`Tree data loaded: ${dataUrl}`);
  } catch (error) {
    setNote(`Could not load rollout tree data: ${error.message}`, true);
  }
}

function getDataUrl() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('data')) return params.get('data');
  if (params.get('sample') === 'first3') return '/data/logos_rollout_1k_first3.tree.json';
  return '/data/logos_rollout_1k_all.tree.json';
}

function renderCoordinates() {
  coordTop.innerHTML = LETTERS.map(letter => `<span>${letter}</span>`).join('');
  coordBottom.innerHTML = coordTop.innerHTML;
  const nums = Array.from({ length: 19 }, (_, index) => 19 - index);
  coordLeft.innerHTML = nums.map(number => `<span>${number}</span>`).join('');
  coordRight.innerHTML = coordLeft.innerHTML;
}

function renderBoard() {
  boardEl.innerHTML = '';

  for (let row = 0; row < 19; row += 1) {
    for (let col = 0; col < 19; col += 1) {
      const pos = `${LETTERS[col]}${19 - row}`;
      const point = document.createElement('button');
      point.type = 'button';
      point.className = 'point';
      point.dataset.pos = pos;
      point.setAttribute('role', 'gridcell');
      point.setAttribute('aria-label', pos);
      if (isStarPoint(row, col)) point.classList.add('star');
      boardEl.append(point);
    }
  }
}

function bindEvents() {
  sampleSelect.addEventListener('change', () => selectSample(sampleSelect.value));
  branchSelect.addEventListener('change', () => selectBranch(branchSelect.value));
  document.querySelector('#baseBtn').addEventListener('click', () => {
    stepIndex = 0;
    syncBoard();
  });
  document.querySelector('#prevStepBtn').addEventListener('click', () => {
    stepIndex = Math.max(0, stepIndex - 1);
    syncBoard();
  });
  document.querySelector('#nextStepBtn').addEventListener('click', () => {
    stepIndex = Math.min(activeBranch?.steps.length || 0, stepIndex + 1);
    syncBoard();
  });
  reasoningViewBtn.addEventListener('click', () => setTextView('reasoning'));
  inputViewBtn.addEventListener('click', () => setTextView('input'));
}

function populateSamples() {
  sampleSelect.innerHTML = dataset.map(row => {
    const position = getPosition(row);
    const branches = getBranches(row);
    const status = row.parse_metadata?.parse_status || 'parsed';
    return (
      `<option value="${escapeHtml(getSampleId(row))}">` +
      `id ${escapeHtml(getSampleId(row))} · ${position.move_count} moves · ${branches.length} branches · ${status}` +
      '</option>'
    );
  }).join('');
}

function selectSample(id) {
  activeSample = dataset.find(row => getSampleId(row) === id) || dataset[0];
  if (!activeSample) return;

  activeBranches = getBranches(activeSample);
  sampleSelect.value = getSampleId(activeSample);
  branchSelect.disabled = activeBranches.length === 0;
  branchSelect.innerHTML = activeBranches.length
    ? activeBranches.map(branch => (
      `<option value="${escapeHtml(branch.id)}">` +
      `${escapeHtml(branch.id)}: ${escapeHtml(branch.candidate)} · ${branch.steps.length} moves` +
      '</option>'
    )).join('')
    : '<option>No parsed branches</option>';

  renderSourceText();
  renderAnswer();
  selectBranch(activeBranches[0]?.id);
}

function setTextView(view) {
  activeTextView = view;
  renderSourceText();
}

function renderSourceText() {
  if (!activeSample) return;
  const isReasoning = activeTextView === 'reasoning';
  sourceTitle.textContent = isReasoning ? 'Reasoning' : 'Input';
  sourceBox.value = isReasoning
    ? activeSample.reasoning?.raw || activeSample.text?.reasoning || ''
    : activeSample.input?.raw || activeSample.messages?.user || '';
  reasoningViewBtn.setAttribute('aria-pressed', String(isReasoning));
  inputViewBtn.setAttribute('aria-pressed', String(!isReasoning));
}

function selectBranch(id) {
  activeBranch = activeBranches.find(branch => branch.id === id) || activeBranches[0] || null;
  if (activeBranch) branchSelect.value = activeBranch.id;
  stepIndex = 0;
  renderBranchMoves();
  syncBoard();
}

function renderAnswer() {
  const position = getPosition(activeSample);
  const answer = activeSample.answer || {};
  const answerColor = answer.color || '';
  const turnLabel = position.next_color === answerColor ? 'turn ok' : 'turn mismatch';
  const parseStatus = activeSample.parse_metadata?.parse_status || '';

  answerBox.innerHTML = [
    answer.label || joinMove(answerColor, answer.coord) || 'No answer',
    answer.winrate_text || answer.winrate || 'No winrate',
    turnLabel,
    parseStatus
  ].map(item => `<span>${escapeHtml(item)}</span>`).join('');
}

async function syncBoard() {
  if (!activeSample) return;
  const position = getPosition(activeSample);
  const branchMovesForStep = activeBranch ? activeBranch.steps.slice(0, stepIndex) : [];
  const moves = [
    ...getPositionMoves(activeSample).map(move => ({ pos: move.coord, sign: move.color === 'X' ? 1 : -1 })),
    ...branchMovesForStep.map(move => ({ pos: move.coord, sign: move.color === 'X' ? 1 : -1 }))
  ];

  try {
    const response = await fetch('/api/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ moves })
    });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.message || 'Render failed');

    updateStones(data.board, moves.at(-1)?.pos);
    sampleStatus.textContent = `id ${getSampleId(activeSample)} · base ${position.move_count}`;
    branchStatus.textContent = activeBranch
      ? `${activeBranch.id} · ${stepIndex}/${activeBranch.steps.length}`
      : 'No branch';
    renderBranchMoves();
    setNote(`Tree data loaded: ${dataUrl}`);
  } catch (error) {
    setNote(error.message, true);
  }
}

function updateStones(board, lastPos) {
  document.querySelectorAll('.point').forEach(point => {
    const { row, col } = posToRowCol(point.dataset.pos);
    const value = board[row][col];
    point.classList.toggle('black', value === 1);
    point.classList.toggle('white', value === -1);
    point.classList.toggle('last', Boolean(lastPos && lastPos === point.dataset.pos));
  });
}

function renderBranchMoves() {
  if (!activeBranch) {
    branchMoves.innerHTML = '<li>No parsed moves</li>';
    return;
  }

  branchMoves.innerHTML = activeBranch.steps.map((move, index) => {
    const term = getMoveTerm(move);
    const comments = getMoveComments(move, index);
    const classes = [
      index < stepIndex ? 'seen' : '',
      term ? 'has-term' : '',
      move.valid === false ? 'invalid' : ''
    ].filter(Boolean).join(' ');

    return (
      `<li class="${classes}">` +
      '<div class="move-main">' +
      `<button type="button" data-step="${index + 1}">${escapeHtml(formatMove(move))}</button>` +
      `<span class="${term ? 'move-term' : 'move-term empty'}">${escapeHtml(term || 'no term')}</span>` +
      `<span class="move-source">${escapeHtml(move.raw || '')}</span>` +
      '</div>' +
      comments.map(comment => `<div class="move-comment">${escapeHtml(comment)}</div>`).join('') +
      '</li>'
    );
  }).join('');

  branchMoves.querySelectorAll('button').forEach(button => {
    button.addEventListener('click', () => {
      stepIndex = Number(button.dataset.step);
      syncBoard();
    });
  });
}

function getBranches(sample) {
  if (!sample) return [];
  if (sample._branches) return sample._branches;

  if (sample.tree) {
    const paths = [];
    collectTreePaths(sample.tree, [], paths);
    sample._branches = paths.map((path, index) => {
      const steps = path.map(nodeToStep);
      return {
        id: `branch-${index + 1}`,
        nodePath: path.map(node => node.node_id),
        candidate: steps[0] ? formatMove(steps[0]) : 'empty',
        steps
      };
    });
    return sample._branches;
  }

  sample._branches = (sample.branches || []).map((branch, index) => ({
    id: branch.id || `branch-${index + 1}`,
    candidate: branch.candidate || '',
    steps: branch.steps || branch.moves || []
  }));
  return sample._branches;
}

function collectTreePaths(node, path, paths) {
  const children = Array.isArray(node?.children) ? node.children : [];
  if (children.length === 0) {
    if (path.length > 0) paths.push(path);
    return;
  }

  children.forEach(child => collectTreePaths(child, [...path, child], paths));
}

function nodeToStep(node) {
  const move = node.move || {};
  return {
    ...move,
    number: move.ply || move.number,
    term: node.term?.raw || '',
    termSource: node.term?.source || '',
    comment: node.comment || {},
    nodeId: node.node_id
  };
}

function getPosition(sample) {
  if (sample?.position) return sample.position;
  return {
    move_count: sample?.base?.moveCount || 0,
    next_color: sample?.base?.nextColor || '',
    moves: sample?.base?.moves || [],
    board_matrix: sample?.base?.board || null
  };
}

function getPositionMoves(sample) {
  const position = getPosition(sample);
  return (position.moves || []).map(move => ({
    color: move.color,
    coord: move.coord
  }));
}

function getMoveTerm(move) {
  if (typeof move.term === 'string') return move.term;
  return move.term?.raw || move.normalizedTerm || '';
}

function getMoveComments(move, index) {
  const comment = move.comment || {};
  const comments = [];
  if (index === 0 && comment.branch) comments.push(`branch: ${comment.branch}`);
  if (comment.local) comments.push(`comment: ${comment.local}`);
  return comments;
}

function formatMove(move) {
  const number = move.ply || move.number || '?';
  const color = move.color || '?';
  const coord = move.coord || '?';
  return `${number}.${color}-${coord}`;
}

function joinMove(color, coord) {
  return color && coord ? `${color}-${coord}` : '';
}

function getSampleId(sample) {
  return String(sample?.sample_id ?? sample?.id ?? '');
}

function posToRowCol(pos) {
  return {
    row: 19 - Number(pos.slice(1)),
    col: LETTERS.indexOf(pos.slice(0, 1))
  };
}

function isStarPoint(row, col) {
  return [3, 9, 15].includes(row) && [3, 9, 15].includes(col);
}

function setNote(text, isError = false) {
  note.textContent = text;
  note.classList.toggle('error', isError);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
