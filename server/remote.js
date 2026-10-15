// Included in the existing authenticated worker. Payloads remain client-encrypted.
async function remote(q, e, u, c, uid) {
  if(u.pathname==='/api/remote/wake' || u.pathname.startsWith('/api/remote/wake/'))return wake(q,e,u,c,uid);
  const db = e.DB, now = Date.now();
  await db.prepare('CREATE TABLE IF NOT EXISTS remote_devices (user_id TEXT, id TEXT, seen INTEGER, PRIMARY KEY(user_id,id))').run();
  await db.prepare('CREATE TABLE IF NOT EXISTS remote_jobs (user_id TEXT, id TEXT, device TEXT, payload TEXT, stage TEXT, updated INTEGER, created INTEGER, command TEXT, PRIMARY KEY(user_id,id))').run();
  const columns=await db.prepare('PRAGMA table_info(remote_jobs)').all();
  if(!columns.results.some(c=>c.name==='cancel_requested')) {
    try { await db.prepare('ALTER TABLE remote_jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0').run(); }
    catch(error) { const checked=await db.prepare('PRAGMA table_info(remote_jobs)').all(); if(!checked.results.some(c=>c.name==='cancel_requested'))throw error; }
  }
  await db.prepare("CREATE UNIQUE INDEX IF NOT EXISTS remote_one_active ON remote_jobs(user_id,device) WHERE stage IN ('starting','running','waiting_code','review_required')").run();
  await db.prepare("UPDATE remote_jobs SET stage='expired',payload='',command=NULL WHERE user_id=? AND stage='queued' AND created<?").bind(uid,now-900000).run();
  await db.prepare('DELETE FROM remote_jobs WHERE user_id=? AND created<?').bind(uid,now-86400000).run();
  const validId = value => typeof value === 'string' && /^[a-f0-9-]{36}$/i.test(value);
  const encrypted = value => {
    if (typeof value !== 'string' || value.length > 50000) return false;
    try { const b=JSON.parse(value); return b.v===1 && typeof b.iv==='string' && b.iv.length===16 && typeof b.data==='string' && b.data.length>=24; } catch { return false; }
  };
  if(q.method==='GET' && u.pathname==='/api/remote') {
    const devices=await db.prepare('SELECT id,seen FROM remote_devices WHERE user_id=? AND seen>?').bind(uid,now-60000).all();
    const jobs=await db.prepare('SELECT id,device,stage,updated,created,payload,cancel_requested FROM remote_jobs WHERE user_id=? ORDER BY created DESC LIMIT 20').bind(uid).all();
    return res({devices:devices.results,jobs:jobs.results},200,c);
  }
  if(q.method!=='POST') return res({message:'Not found.'},404,c);
  const x=await body(q);
  if(!validId(x.device)) return res({message:'Invalid computer.'},400,c);
  if(u.pathname==='/api/remote/heartbeat') {
    await db.prepare('INSERT INTO remote_devices(user_id,id,seen) VALUES(?,?,?) ON CONFLICT(user_id,id) DO UPDATE SET seen=excluded.seen').bind(uid,x.device,now).run();
    return res({ok:true},200,c);
  }
  if(!validId(x.id)) return res({message:'Invalid request ID.'},400,c);
  if(u.pathname==='/api/remote/submit') {
    if(!encrypted(x.payload)) return res({message:'An encrypted request is required.'},400,c);
    const online=await db.prepare('SELECT id FROM remote_devices WHERE user_id=? AND id=? AND seen>?').bind(uid,x.device,now-60000).first();
    if(!online) return res({message:'Computer is offline. Enable phone requests in the desktop app.'},409,c);
    const old=await db.prepare('SELECT id FROM remote_jobs WHERE user_id=? AND id=?').bind(uid,x.id).first();
    if(old) return res({ok:true,id:old.id},200,c);
    await db.prepare("INSERT INTO remote_jobs(user_id,id,device,payload,stage,updated,created) VALUES(?,?,?,?,'queued',?,?)").bind(uid,x.id,x.device,x.payload,now,now).run();
    return res({ok:true,id:x.id},201,c);
  }
  if(u.pathname==='/api/remote/cancel') {
    const row=await db.prepare("UPDATE remote_jobs SET cancel_requested=1,command=NULL,stage=CASE WHEN stage='queued' THEN 'cancelled' ELSE stage END,payload=CASE WHEN stage='queued' THEN '' ELSE payload END WHERE user_id=? AND id=? AND device=? AND stage IN ('queued','starting','running','waiting_code','review_required') RETURNING id").bind(uid,x.id,x.device).first();
    return res(row?{ok:true}:{message:'This task has already ended.'},row?200:409,c);
  }
  if(u.pathname==='/api/remote/claim') {
    const active=await db.prepare("SELECT id FROM remote_jobs WHERE user_id=? AND device=? AND stage IN ('starting','running','waiting_code','review_required')").bind(uid,x.device).first();
    if(active) return res({job:null},200,c);
    const job=await db.prepare("UPDATE remote_jobs SET stage='starting',updated=? WHERE user_id=? AND id=? AND device=? AND stage='queued' AND cancel_requested=0 RETURNING id,payload").bind(now,uid,x.id,x.device).first();
    return res({job:job||null},200,c);
  }
  if(u.pathname==='/api/remote/update') {
    const stages=['running','waiting_code','review_required','complete','attention','cancelled'];
    if(!stages.includes(x.stage)) return res({message:'Invalid stage.'},400,c);
    if(x.payload !== undefined && !encrypted(x.payload)) return res({message:'Encrypted status required.'},400,c);
    await db.prepare("UPDATE remote_jobs SET stage=?,updated=?,payload=? WHERE user_id=? AND id=? AND device=? AND stage IN ('starting','running','waiting_code','review_required')").bind(x.stage,now,x.payload || '',uid,x.id,x.device).run();
    return res({ok:true},200,c);
  }
  if(u.pathname==='/api/remote/approve') {
    if(!encrypted(x.payload)) return res({message:'Encrypted approval required.'},400,c);
    const row=await db.prepare("UPDATE remote_jobs SET command=? WHERE user_id=? AND id=? AND device=? AND stage='review_required' AND cancel_requested=0 AND command IS NULL RETURNING id").bind(x.payload,uid,x.id,x.device).first();
    return res(row?{ok:true}:{message:'Review is no longer waiting, or approval is already pending.'},row?200:409,c);
  }
  if(u.pathname==='/api/remote/take-approval') {
    const row=await db.prepare("SELECT command FROM remote_jobs WHERE user_id=? AND id=? AND device=? AND stage='review_required'").bind(uid,x.id,x.device).first();
    if(!row?.command) return res({payload:null},200,c);
    const taken=await db.prepare('UPDATE remote_jobs SET command=NULL WHERE user_id=? AND id=? AND device=? AND command=? RETURNING id').bind(uid,x.id,x.device,row.command).first();
    return res({payload:taken?row.command:null},200,c);
  }
  if(u.pathname==='/api/remote/code') {
    if(!encrypted(x.payload)) return res({message:'Encrypted code required.'},400,c);
    const row=await db.prepare("UPDATE remote_jobs SET command=? WHERE user_id=? AND id=? AND device=? AND stage='waiting_code' AND cancel_requested=0 AND command IS NULL RETURNING id").bind(x.payload,uid,x.id,x.device).first();
    return res(row?{ok:true}:{message:'This task is not waiting for a code, or a code is already pending.'},row?200:409,c);
  }
  if(u.pathname==='/api/remote/take-code') {
    // Atomically remove before returning: a lost response cannot duplicate a code submission.
    const row=await db.prepare("SELECT command FROM remote_jobs WHERE user_id=? AND id=? AND device=? AND stage='waiting_code'").bind(uid,x.id,x.device).first();
    if(!row?.command) return res({payload:null},200,c);
    const taken=await db.prepare('UPDATE remote_jobs SET command=NULL WHERE user_id=? AND id=? AND device=? AND command=? RETURNING id').bind(uid,x.id,x.device,row.command).first();
    return res({payload:taken?row.command:null},200,c);
  }
  return res({message:'Not found.'},404,c);
}

