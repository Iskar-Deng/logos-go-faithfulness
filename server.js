const express = require('express');
const path = require('path');
const { quickBatchMove, quickBatchCheck, normalizeMoves } = require('./src/gogame');

const app = express();
const port = Number(process.env.PORT || 4173);
const host = process.env.HOST || '127.0.0.1';

app.use(express.json({ limit: '1mb' }));
app.use(express.static(path.join(__dirname, 'public')));

app.get('/', (_req, res) => {
  res.redirect('/rollout.html');
});

app.post('/api/render', (req, res) => {
  try {
    const moves = normalizeMoves(req.body.moves || []);
    const result = quickBatchMove(moves);
    const legality = quickBatchCheck(moves);

    res.json({
      ...result,
      legality
    });
  } catch (error) {
    res.status(400).json({ success: false, message: error.message });
  }
});

app.listen(port, host, () => {
  console.log(`LoGos goGame local playground: http://${host}:${port}`);
});
