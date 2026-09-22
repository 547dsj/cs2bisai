const ADMIN_HASH = '78ed6853e605505b87da90dfeec22a89:100000:54802443a828251e6bcf142844f7972e77eeb1be0e9fc072b127e0be4a868c5a';
const COOKIE = 'cs2_admin_session';
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Allow-Credentials': 'true',
};
const enc = new TextEncoder();
const dec = new TextDecoder();

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json;charset=utf-8', ...CORS, ...headers } });
}
const hex = (b) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, '0')).join('');
const unhex = (s) => new Uint8Array(s.match(/.{2}/g).map((x) => parseInt(x, 16)));

async function verifyPassword(pw, stored) {
  try {
    const [salt, iter, hash] = stored.split(':');
    const key = await crypto.subtle.importKey('raw', enc.encode(pw), 'PBKDF2', false, ['deriveBits']);
    const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: unhex(salt), iterations: Number(iter) }, key, 256);
    return hex(bits) === hash;
  } catch { return false; }
}
async function hmac(v, secret) {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return hex(await crypto.subtle.sign('HMAC', key, enc.encode(v)));
}
function cookies(req) {
  const out = {};
  for (const part of (req.headers.get('Cookie') || '').split(';')) {
    const i = part.indexOf('=');
    if (i > -1) out[part.slice(0, i).trim()] = part.slice(i + 1).trim();
  }
  return out;
}
async function sessionOk(req, secret) {
  const raw = cookies(req)[COOKIE];
  if (!raw) return false;
  const p = raw.split('.');
  if (p.length !== 3) return false;
  if (Number(p[1]) < Math.floor(Date.now() / 1000)) return false;
  return (await hmac(`${p[0]}.${p[1]}`, secret)) === p[2];
}
async function newSession(secret) {
  const token = crypto.randomUUID();
  const exp = Math.floor(Date.now() / 1000) + 7 * 24 * 3600;
  return `${token}.${exp}.${await hmac(`${token}.${exp}`, secret)}`;
}
function ip(req) {
  return (req.headers.get('CF-Connecting-IP') || req.headers.get('X-Forwarded-For') || '').split(',')[0].trim() || 'unknown';
}
async function rate(env, key, limit, win) {
  const now = Math.floor(Date.now() / 1000);
  const row = await env.DB.prepare('SELECT count, reset_at FROM rate_limits WHERE key = ?').bind(key).first();
  if (row && row.reset_at > now && row.count >= limit) return false;
  if (!row || row.reset_at <= now) {
    await env.DB.prepare('INSERT INTO rate_limits(key, count, reset_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET count=1, reset_at=?').bind(key, 1, now + win, now + win).run();
  } else {
    await env.DB.prepare('UPDATE rate_limits SET count=count+1 WHERE key=?').bind(key).run();
  }
  return true;
}
async function touch(env) {
  const now = new Date().toISOString().slice(0, 19).replace('T', ' ');
  await env.DB.prepare('INSERT INTO site_settings(setting_key,setting_value) VALUES(?,?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=?').bind('last_modified', now, now).run();
}
function event(row) {
  if (!row) return null;
  let a = [], b = [];
  try { a = JSON.parse(row.champion_roster || '[]'); } catch {}
  try { b = JSON.parse(row.runnerup_roster || '[]'); } catch {}
  return { id: row.id, name: row.name, org: row.org, level: row.level, start_date: row.start_date, end_date: row.end_date, location: row.location, prize: row.prize, champion: row.champion, runnerup: row.runnerup, mvp: row.mvp, score: row.score, champion_roster: a, runnerup_roster: b };
}
async function adminOnly(req, env) {
  if (!(await sessionOk(req, env.SESSION_SECRET || 'dev-secret'))) throw { status: 401, detail: '请先登录' };
}
export async function onRequest(ctx) {
  const req = ctx.request, env = ctx.env;
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
  try {
    if (!(await rate(env, `${ip(req)}:api`, 240, 60))) return json({ detail: '请求过于频繁，请稍后再试' }, 429);
    const p = new URL(req.url).pathname.replace(/^\/api\/?/, '').split('/').filter(Boolean);
    if (p[0] === 'admin') {
      if (p[1] === 'login' && req.method === 'POST') {
        if (!(await rate(env, `${ip(req)}:login`, 5, 900))) return json({ detail: '尝试次数过多，请稍后再试' }, 429);
        const b = await req.json().catch(() => ({}));
        if (!(await verifyPassword(String(b.password || ''), env.ADMIN_PASSWORD_HASH || ADMIN_HASH))) return json({ detail: '密码错误' }, 401);
        const s = await newSession(env.SESSION_SECRET || 'dev-secret');
        const secure = new URL(req.url).protocol === 'https:' ? '; Secure' : '';
        return json({ authenticated: true }, 200, { 'Set-Cookie': `${COOKIE}=${s}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${7 * 24 * 3600}${secure}` });
      }
      if (p[1] === 'logout') return json({ authenticated: false }, 200, { 'Set-Cookie': `${COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0` });
      if (p[1] === 'check') return json({ authenticated: await sessionOk(req, env.SESSION_SECRET || 'dev-secret') });
    }
    if (p[0] === 'settings' && req.method === 'GET') {
      const r = await env.DB.prepare("SELECT setting_value FROM site_settings WHERE setting_key='last_modified'").first();
      return json({ last_modified: r ? r.setting_value : null });
    }
    if (p[0] === 'events') {
      if (req.method === 'GET' && p.length === 1) {
        const { results } = await env.DB.prepare('SELECT * FROM events ORDER BY start_date ASC, id ASC').all();
        return json(results.map(event));
      }
      if (req.method === 'GET' && p.length === 2) {
        const r = await env.DB.prepare('SELECT * FROM events WHERE id=?').bind(Number(p[1])).first();
        return r ? json(event(r)) : json({ detail: '赛事不存在' }, 404);
      }
      if (req.method === 'POST') {
        await adminOnly(req, env);
        const b = await req.json();
        const cr = JSON.stringify(b.champion_roster || []), rr = JSON.stringify(b.runnerup_roster || []);
        const info = await env.DB.prepare('INSERT INTO events(name,org,level,start_date,end_date,location,prize,champion,runnerup,mvp,score,champion_roster,runnerup_roster) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)').bind(b.name,b.org,b.level,b.start_date,b.end_date,b.location,Number(b.prize),b.champion||null,b.runnerup||null,b.mvp||null,b.score||null,cr,rr).run();
        await touch(env);
        const r = await env.DB.prepare('SELECT * FROM events WHERE id=?').bind(info.meta.last_row_id).first();
        return json(event(r), 201);
      }
      if (p.length === 2 && (req.method === 'PUT' || req.method === 'DELETE')) {
        await adminOnly(req, env);
        const id = Number(p[1]);
        if (req.method === 'DELETE') {
          await env.DB.prepare('DELETE FROM events WHERE id=?').bind(id).run();
          await touch(env);
          return new Response(null, { status: 204 });
        }
        const b = await req.json();
        const cr = JSON.stringify(b.champion_roster || []), rr = JSON.stringify(b.runnerup_roster || []);
        await env.DB.prepare('UPDATE events SET name=?,org=?,level=?,start_date=?,end_date=?,location=?,prize=?,champion=?,runnerup=?,mvp=?,score=?,champion_roster=?,runnerup_roster=? WHERE id=?').bind(b.name,b.org,b.level,b.start_date,b.end_date,b.location,Number(b.prize),b.champion||null,b.runnerup||null,b.mvp||null,b.score||null,cr,rr,id).run();
        await touch(env);
        const r = await env.DB.prepare('SELECT * FROM events WHERE id=?').bind(id).first();
        return r ? json(event(r)) : json({ detail: '赛事不存在' }, 404);
      }
    }
    return json({ detail: '接口不存在' }, 404);
  } catch (e) {
    if (e && e.status) return json({ detail: e.detail || 'error' }, e.status);
    return json({ detail: '服务器错误' }, 500);
  }
}