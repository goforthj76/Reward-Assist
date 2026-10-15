// Include beside remote.js. Owner routes require the existing authenticated uid.
// Route /api/wake/tablet/* here BEFORE account auth; it uses a wake-only capability.
async function wake(q, e, u, c, uid = null) {
  const db=e.DB, now=Date.now(), reply=(v,s=200)=>res(v,s,c);
  const id=v=>typeof v==='string' && /^[a-f0-9-]{36}$/i.test(v);
  await db.prepare('CREATE TABLE IF NOT EXISTS wake_relays (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, device TEXT NOT NULL, token_hash TEXT NOT NULL, expires INTEGER NOT NULL, seen INTEGER NOT NULL DEFAULT 0, request_id TEXT, requested INTEGER, claimed INTEGER, result TEXT)').run();
  const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))),v=>v.toString(16).padStart(2,'0')).join('');
  const tablet=u.pathname.startsWith('/api/wake/tablet/');
  if(tablet) {
    if(q.method!=='POST')return reply({message:'Not found.'},404);
    const token=(q.headers.get('Authorization')||'').replace(/^Bearer /,'');
    if(!/^[a-f0-9-]{36}\.[a-f0-9]{64}$/i.test(token))return reply({message:'Pair the tablet again.'},401);
    const relay=await db.prepare('SELECT * FROM wake_relays WHERE id=? AND token_hash=? AND expires>?').bind(token.slice(0,36),await hash(token),now).first();
    if(!relay)return reply({message:'Pairing expired or was removed.'},401);
    if(u.pathname==='/api/wake/tablet/poll') {
      await db.prepare('UPDATE wake_relays SET seen=? WHERE id=?').bind(now,relay.id).run();
      // Consume before delivery. A lost response expires rather than replaying a stale wake.
      const job=await db.prepare("UPDATE wake_relays SET claimed=?,result='sending' WHERE id=? AND requested>? AND claimed IS NULL AND request_id IS NOT NULL RETURNING request_id").bind(now,relay.id,now-120000).first();
      return reply({request:job?.request_id||null});
    }
    if(u.pathname==='/api/wake/tablet/ack') {
      const x=await body(q);
      if(!id(x.id)||!['sent','failed'].includes(x.result))return reply({message:'Invalid acknowledgement.'},400);
      await db.prepare("UPDATE wake_relays SET result=? WHERE id=? AND request_id=? AND claimed IS NOT NULL AND requested>? AND result='sending'").bind(x.result,relay.id,x.id,now-120000).run();
      return reply({ok:true});
    }
    return reply({message:'Not found.'},404);
  }
  if(!uid)return reply({message:'Sign in first.'},401);
  if(q.method==='GET' && u.pathname==='/api/remote/wake') {
    const rows=await db.prepare('SELECT id,device,seen,expires,request_id,requested,result FROM wake_relays WHERE user_id=? AND expires>?').bind(uid,now).all();
    return reply({relays:rows.results.map(r=>({...r,online:r.seen>now-90000,result:r.requested && r.requested<now-120000 && !['sent','failed'].includes(r.result)?'expired':r.result}))});
  }
  if(q.method!=='POST')return reply({message:'Not found.'},404);
  const x=await body(q);
  if(u.pathname==='/api/remote/wake/register') {
    if(!id(x.device))return reply({message:'Choose a known computer.'},400);
    const owned=await db.prepare('SELECT id FROM remote_devices WHERE user_id=? AND id=?').bind(uid,x.device).first();
    if(!owned)return reply({message:'Enable phone requests on this computer first.'},409);
    const relay=crypto.randomUUID(), secret=Array.from(crypto.getRandomValues(new Uint8Array(32)),v=>v.toString(16).padStart(2,'0')).join(''), token=relay+'.'+secret;
    // One tablet per computer; pairing again revokes the old token.
    await db.prepare('DELETE FROM wake_relays WHERE user_id=? AND device=?').bind(uid,x.device).run();
    await db.prepare('INSERT INTO wake_relays(id,user_id,device,token_hash,expires) VALUES(?,?,?,?,?)').bind(relay,uid,x.device,await hash(token),now+90*86400000).run();
    return reply({id:relay,token,expires:now+90*86400000},201);
  }
  if(!id(x.relay))return reply({message:'Invalid tablet.'},400);
  if(u.pathname==='/api/remote/wake/revoke') {
    await db.prepare('DELETE FROM wake_relays WHERE id=? AND user_id=?').bind(x.relay,uid).run();return reply({ok:true});
  }
  if(u.pathname==='/api/remote/wake/request') {
    if(!id(x.id))return reply({message:'Invalid request.'},400);
    const row=await db.prepare('SELECT * FROM wake_relays WHERE id=? AND user_id=? AND expires>?').bind(x.relay,uid,now).first();
    if(!row)return reply({message:'Pair a tablet first.'},404);
    if(row.request_id===x.id)return reply({ok:true,id:x.id});
    if(row.seen<now-90000)return reply({message:'Tablet is offline. Open Wake Relay on the tablet.'},409);
    const changed=await db.prepare("UPDATE wake_relays SET request_id=?,requested=?,claimed=NULL,result='queued' WHERE id=? AND user_id=? AND (requested IS NULL OR requested<?) RETURNING id").bind(x.id,now,x.relay,uid,now-30000).first();
    return changed?reply({ok:true,id:x.id},201):reply({message:'A wake request was just sent. Wait 30 seconds.'},429);
  }
  return reply({message:'Not found.'},404);
}
