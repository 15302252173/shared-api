const mysql = require('mysql2/promise');
const express = require('express');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3456;

app.use(cors());
app.use(express.json());

// MySQL pool
let pool;

async function getPool() {
  if (!pool) {
    pool = mysql.createPool({
      host: '154.201.90.148',
      port: 3306,
      user: 'niu_api',
      password: 'Niu2Xiao8@2026!',
      database: 'niu_workspace',
      charset: 'utf8mb4',
      waitForConnections: true,
      connectionLimit: 5,
    });
  }
  return pool;
}

// ═══════════ API Routes ═══════════

app.get('/api/health', async (req, res) => {
  try {
    const p = await getPool();
    await p.query('SELECT 1');
    res.json({ status: 'ok', agent: '小牛×小八 共享工作台', time: new Date().toISOString(), db: 'MySQL@154.201.90.148' });
  } catch(e) {
    res.json({ status: 'error', message: e.message });
  }
});

// ── TODOS ──
app.get('/api/todos', async (req, res) => {
  try {
    const p = await getPool();
    const { user_id, date } = req.query;
    let sql = 'SELECT * FROM todos WHERE 1=1';
    const params = [];
    if (user_id) { sql += ' AND user_id = ?'; params.push(user_id); }
    if (date) { sql += ' AND date = ?'; params.push(date); }
    sql += ' ORDER BY sort_order ASC, priority, created_at DESC';
    const [rows] = await p.query(sql, params);
    res.json(rows);
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/todos', async (req, res) => {
  try {
    const p = await getPool();
    const { user_id, agent_id, text, date, priority, estimated_minutes } = req.body;
    const [result] = await p.query(
      'INSERT INTO todos (user_id, agent_id, text, date, priority, estimated_minutes) VALUES (?, ?, ?, ?, ?, ?)',
      [user_id || 1, agent_id || null, text, date, priority || 'medium', estimated_minutes || null]
    );
    res.json({ id: result.insertId, ...req.body });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.put('/api/todos/:id', async (req, res) => {
  try {
    const p = await getPool();
    const { done, text, priority, sort_order } = req.body;
    if (done !== undefined) {
      await p.query('UPDATE todos SET done = ?, completed_at = NOW() WHERE id = ?', [done ? 1 : 0, req.params.id]);
    }
    if (text !== undefined) await p.query('UPDATE todos SET text = ? WHERE id = ?', [text, req.params.id]);
    if (priority) await p.query('UPDATE todos SET priority = ? WHERE id = ?', [priority, req.params.id]);
    if (sort_order !== undefined) await p.query('UPDATE todos SET sort_order = ? WHERE id = ?', [sort_order, req.params.id]);
    res.json({ success: true });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// Bulk reorder
app.put('/api/todos', async (req, res) => {
  try {
    const p = await getPool();
    const { order } = req.body;
    if (order && Array.isArray(order)) {
      for (const item of order) {
        await p.query('UPDATE todos SET sort_order = ? WHERE id = ?', [item.sort_order, item.id]);
      }
    }
    res.json({ success: true });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.delete('/api/todos/:id', async (req, res) => {
  try {
    await (await getPool()).query('DELETE FROM todos WHERE id = ?', [req.params.id]);
    res.json({ success: true });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// ── IDEAS ──
app.get('/api/ideas', async (req, res) => {
  try {
    const p = await getPool();
    const { user_id, status } = req.query;
    let sql = 'SELECT * FROM ideas WHERE 1=1';
    const params = [];
    if (user_id) { sql += ' AND user_id = ?'; params.push(user_id); }
    if (status) { sql += ' AND status = ?'; params.push(status); }
    sql += ' ORDER BY priority, created_at DESC';
    const [rows] = await p.query(sql, params);
    res.json(rows);
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/ideas', async (req, res) => {
  try {
    const p = await getPool();
    const { user_id, agent_id, title, description, category, priority, source_agent } = req.body;
    const [result] = await p.query(
      'INSERT INTO ideas (user_id, agent_id, title, description, category, priority, source_agent) VALUES (?, ?, ?, ?, ?, ?, ?)',
      [user_id || 1, agent_id || null, title, description, category, priority || 'medium', source_agent || '小牛']
    );
    res.json({ id: result.insertId, ...req.body });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.put('/api/ideas/:id', async (req, res) => {
  try {
    const p = await getPool();
    const { status, title, description, sort_order, priority, category } = req.body;
    if (status) await p.query('UPDATE ideas SET status = ? WHERE id = ?', [status, req.params.id]);
    if (title) await p.query('UPDATE ideas SET title = ? WHERE id = ?', [title, req.params.id]);
    if (description) await p.query('UPDATE ideas SET description = ? WHERE id = ?', [description, req.params.id]);
    if (sort_order !== undefined) await p.query('UPDATE ideas SET sort_order = ? WHERE id = ?', [sort_order, req.params.id]);
    if (priority) await p.query('UPDATE ideas SET priority = ? WHERE id = ?', [priority, req.params.id]);
    if (category !== undefined) await p.query('UPDATE ideas SET category = ? WHERE id = ?', [category, req.params.id]);
    res.json({ success: true });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.delete('/api/ideas/:id', async (req, res) => {
  try {
    await (await getPool()).query('DELETE FROM ideas WHERE id = ?', [req.params.id]);
    res.json({ success: true });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

// ── LEARNING ──
app.get('/api/learning', async (req, res) => {
  try {
    const p = await getPool();
    const { user_id, status } = req.query;
    let sql = 'SELECT * FROM learning_items WHERE 1=1';
    const params = [];
    if (user_id) { sql += ' AND user_id = ?'; params.push(user_id); }
    if (status) { sql += ' AND status = ?'; params.push(status); }
    sql += ' ORDER BY priority, created_at DESC';
    const [rows] = await p.query(sql, params);
    res.json(rows);
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.post('/api/learning', async (req, res) => {
  try {
    const p = await getPool();
    const { user_id, agent_id, title, url, description, category, priority, estimated_hours, estimated_minutes, source_agent } = req.body;
    const hours = estimated_hours ?? (estimated_minutes != null ? estimated_minutes / 60 : null);
    const minutes = estimated_minutes ?? (estimated_hours != null ? estimated_hours * 60 : null);
    const [result] = await p.query(
      'INSERT INTO learning_items (user_id, agent_id, title, url, description, category, priority, estimated_hours, estimated_minutes, source_agent) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
      [user_id || 1, agent_id || null, title, url, description, category, priority || 'medium', hours, minutes, source_agent || '小牛']
    );
    res.json({ id: result.insertId, ...req.body });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.put('/api/learning/:id', async (req, res) => {
  try {
    const p = await getPool();
    const { status, title, url, description, notes, sort_order, estimated_minutes, estimated_hours, priority, category } = req.body;
    if (status) await p.query('UPDATE learning_items SET status = ? WHERE id = ?', [status, req.params.id]);
    if (title) await p.query('UPDATE learning_items SET title = ? WHERE id = ?', [title, req.params.id]);
    if (url) await p.query('UPDATE learning_items SET url = ? WHERE id = ?', [url, req.params.id]);
    if (description) await p.query('UPDATE learning_items SET description = ? WHERE id = ?', [description, req.params.id]);
    if (notes) await p.query('UPDATE learning_items SET notes = ? WHERE id = ?', [notes, req.params.id]);
    if (sort_order !== undefined) await p.query('UPDATE learning_items SET sort_order = ? WHERE id = ?', [sort_order, req.params.id]);
    if (priority) await p.query('UPDATE learning_items SET priority = ? WHERE id = ?', [priority, req.params.id]);
    if (category !== undefined) await p.query('UPDATE learning_items SET category = ? WHERE id = ?', [category, req.params.id]);
    // Keep estimated_minutes and estimated_hours in sync
    if (estimated_minutes !== undefined) {
      await p.query('UPDATE learning_items SET estimated_minutes = ?, estimated_hours = ? WHERE id = ?', [estimated_minutes, estimated_minutes / 60, req.params.id]);
    } else if (estimated_hours !== undefined) {
      await p.query('UPDATE learning_items SET estimated_hours = ?, estimated_minutes = ? WHERE id = ?', [estimated_hours, estimated_hours * 60, req.params.id]);
    }
    res.json({ success: true });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.delete('/api/learning/:id', async (req, res) => {
  try {
    await (await getPool()).query('DELETE FROM learning_items WHERE id = ?', [req.params.id]);
    res.json({ success: true });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.get('/api/stats', async (req, res) => {
  try {
    const p = await getPool();
    const uid = req.query.user_id;
    const today = new Date().toISOString().slice(0, 10);
    const todoFilter = uid ? 'WHERE user_id = ? AND date = ?' : 'WHERE date = ?';
    const ideaFilter = uid ? 'WHERE user_id = ? AND status NOT IN ("done","archived")' : 'WHERE status NOT IN ("done","archived")';
    const learnFilter = uid ? 'WHERE user_id = ? AND status IN ("todo","in_progress")' : 'WHERE status IN ("todo","in_progress")';
    const todoParams = uid ? [uid, today] : [today];
    const ideaParams = uid ? [uid] : [];
    const learnParams = uid ? [uid] : [];
    const [todos] = await p.query(`SELECT COUNT(*) as total, SUM(CASE WHEN done=1 THEN 1 ELSE 0 END) as done FROM todos ${todoFilter}`, todoParams);
    const [ideas] = await p.query(`SELECT COUNT(*) as active FROM ideas ${ideaFilter}`, ideaParams);
    const [learn] = await p.query(`SELECT COUNT(*) as active FROM learning_items ${learnFilter}`, learnParams);
    res.json({ todos: todos[0], ideas_active: ideas[0].active, learning_active: learn[0].active });
  } catch(e) { res.status(500).json({ error: e.message }); }
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🐮 小牛×小八 共享工作台 → http://127.0.0.1:${PORT}`);
  console.log('   MySQL@154.201.90.148 | 小牛🐮 ↔ 小八🐙');
});
