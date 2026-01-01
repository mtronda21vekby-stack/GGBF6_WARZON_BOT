(() => {
  const tg = window.Telegram?.WebApp;
  const $ = (id) => document.getElementById(id);

  const qs = new URLSearchParams(location.search);
  const profile = {
    game: qs.get("game") || "zombies",
    platform: qs.get("platform") || "pc",
    input: qs.get("input") || "controller",
    difficulty: qs.get("difficulty") || "pro",
    voice: qs.get("voice") || "TEAMMATE",
    role: qs.get("role") || "slayer",
  };

  const canvas = $("c");
  const ctx = canvas.getContext("2d");
  let W=0,H=0,dpr=1;

  function resize(){
    dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    const rect = canvas.getBoundingClientRect();
    W = Math.floor(rect.width * dpr);
    H = Math.floor(rect.height * dpr);
    canvas.width = W; canvas.height = H;
  }

  function rnd(min,max){ return min + Math.random()*(max-min); }
  function clamp(v,a,b){ return Math.max(a, Math.min(b, v)); }
  function dist2(ax,ay,bx,by){ const dx=ax-bx, dy=ay-by; return dx*dx+dy*dy; }

  function diffK(){
    const d = profile.difficulty || "pro";
    if (d === "normal") return 0.90;
    if (d === "demon") return 1.22;
    return 1.05;
  }

  // --- Player / Weapons / Perks ---
  const weapons = {
    pistol: { name:"Pistol", dmg: 14, fireRate: 3.2, mag: 12, reloadMs: 1100, bulletSpd: 980, spread: 0.11 },
    smg:    { name:"SMG",    dmg: 10, fireRate: 8.5, mag: 28, reloadMs: 1250, bulletSpd: 1060, spread: 0.15 },
    ar:     { name:"AR",     dmg: 16, fireRate: 6.2, mag: 24, reloadMs: 1400, bulletSpd: 1180, spread: 0.10 },
  };

  const perkDefs = {
    jug: { name:"Juggernaut", desc:"+50% HP", cost:2000 },
    speedcola: { name:"Speed Cola", desc:"-25% reload", cost:1500 },
  };

  const shopItems = [
    { id:"smg", type:"weapon", cost: 600, title:"SMG", sub:"Fast control • 28 mag" },
    { id:"ar", type:"weapon", cost: 1400, title:"AR", sub:"Elite dmg • 24 mag" },
    { id:"jug", type:"perk", cost: perkDefs.jug.cost, title:"Juggernaut", sub: perkDefs.jug.desc },
    { id:"speedcola", type:"perk", cost: perkDefs.speedcola.cost, title:"Speed Cola", sub: perkDefs.speedcola.desc },
    { id:"ammo", type:"util", cost: 250, title:"Ammo Refill", sub:"Refill current mag" },
  ];

  let running=false;
  let tStart=0;
  let lastFrame=0;

  const player = {
    x: 0, y: 0,
    r: 14,
    hp: 100,
    maxHp: 100,
    spd: 240, // px/s (dpr-scaled later)
    coins: 0,
    weaponId: "pistol",
    mag: weapons.pistol.mag,
    reloading: false,
    reloadEnd: 0,
    perks: new Set(),
    aimX: 0, aimY: 0
  };

  let wave = 1;
  let waveKills = 0;
  let waveTargetKills = 12;
  let zombies = [];
  let bullets = [];
  let powerups = [];
  let killCount = 0;

  // input
  let joyActive = false;
  let joyId = null;
  let joyCX=0, joyCY=0;
  let joyVX=0, joyVY=0;

  let fireActive = false;
  let lastShotAt = 0;

  function setStatus(s, color){
    $("status").textContent = s;
    if (color) $("status").style.color = color;
  }

  function setHUD(){
    $("hp").textContent = `${Math.max(0, Math.round(player.hp))}/${Math.round(player.maxHp)}`;
    $("coins").textContent = String(player.coins);
    $("wave").textContent = String(wave);
    $("shopCoins").textContent = String(player.coins);
  }

  function applyPerks(){
    player.maxHp = 100;
    let reloadMul = 1.0;
    if (player.perks.has("jug")) player.maxHp = 150;
    if (player.perks.has("speedcola")) reloadMul *= 0.75;
    return { reloadMul };
  }

  function currentWeapon(){
    return weapons[player.weaponId] || weapons.pistol;
  }

  function reloadNow(){
    if (player.reloading) return;
    const w = currentWeapon();
    if (player.mag >= w.mag) return;
    const { reloadMul } = applyPerks();
    player.reloading = true;
    player.reloadEnd = performance.now() + (w.reloadMs * reloadMul);
    setStatus("Перезарядка…", "var(--mut)");
  }

  function finishReloadIfReady(now){
    if (!player.reloading) return;
    if (now >= player.reloadEnd){
      const w = currentWeapon();
      player.mag = w.mag;
      player.reloading = false;
      setStatus("Готов. Доминируй 👑", "var(--ok)");
    }
  }

  function spawnWave(){
    waveKills = 0;
    waveTargetKills = Math.round((10 + wave*2.6) * diffK());
    const count = Math.round((6 + wave*1.6) * diffK());
    const typeChanceFast = clamp(0.10 + wave*0.02, 0.10, 0.35);
    const typeChanceTank = clamp(-0.05 + wave*0.015, 0, 0.18);

    for (let i=0;i<count;i++){
      const edge = Math.floor(rnd(0,4));
      let x,y;
      if (edge===0){ x=rnd(0,W); y=-40*dpr; }
      if (edge===1){ x=W+40*dpr; y=rnd(0,H); }
      if (edge===2){ x=rnd(0,W); y=H+40*dpr; }
      if (edge===3){ x=-40*dpr; y=rnd(0,H); }

      let kind="normal";
      const r = Math.random();
      if (r < typeChanceTank) kind="tank";
      else if (r < typeChanceTank + typeChanceFast) kind="fast";

      const base = (kind==="fast") ? 92 : (kind==="tank") ? 220 : 130;
      const spd = (kind==="fast") ? rnd(118, 160) : (kind==="tank") ? rnd(62, 82) : rnd(78, 110);
      const dmg = (kind==="fast") ? 9 : (kind==="tank") ? 16 : 12;

      zombies.push({
        x,y,
        r: (kind==="tank") ? 18*dpr : 15*dpr,
        hp: Math.round((base + wave*10) * diffK()),
        spd: spd * dpr,
        dmg: dmg,
        kind,
        hitFlash: 0
      });
    }

    setStatus(`Волна ${wave}. Цель убийств: ${waveTargetKills}`, "var(--ok)");
  }

  function maybeDropPowerup(x,y){
    // редкий дроп — элитно, но не ломает баланс
    const p = Math.random();
    if (p < 0.06){
      const types = ["double_points","insta_kill","max_ammo"];
      const type = types[Math.floor(Math.random()*types.length)];
      powerups.push({ x,y, r: 12*dpr, type, born: performance.now(), ttl: 12000 });
    }
  }

  // powerup state
  let doublePointsUntil = 0;
  let instaKillUntil = 0;

  function powerupMul(now){
    return (now < doublePointsUntil) ? 2 : 1;
  }
  function isInstaKill(now){
    return now < instaKillUntil;
  }

  function collectPowerup(pu){
    const now = performance.now();
    if (pu.type === "double_points") doublePointsUntil = now + 15000;
    if (pu.type === "insta_kill") instaKillUntil = now + 10000;
    if (pu.type === "max_ammo") {
      const w = currentWeapon();
      player.mag = w.mag;
      player.reloading = false;
    }
    setStatus(`Power-up: ${pu.type.replace("_"," ").toUpperCase()}`, "var(--warn)");
  }

  function shootToward(ax, ay){
    if (!running) return;
    const now = performance.now();
    const w = currentWeapon();

    finishReloadIfReady(now);
    if (player.reloading) return;

    const shotDelay = (1000 / w.fireRate);
    if (now - lastShotAt < shotDelay) return;

    if (player.mag <= 0){
      reloadNow();
      return;
    }

    lastShotAt = now;
    player.mag--;

    // direction
    let dx = ax - player.x;
    let dy = ay - player.y;
    const len = Math.sqrt(dx*dx+dy*dy) || 1;
    dx/=len; dy/=len;

    // spread
    const s = w.spread * diffK();
    const ang = Math.atan2(dy,dx) + rnd(-s, s);
    dx = Math.cos(ang); dy = Math.sin(ang);

    bullets.push({
      x: player.x + dx*(player.r+6*dpr),
      y: player.y + dy*(player.r+6*dpr),
      vx: dx * w.bulletSpd * dpr / 1000,
      vy: dy * w.bulletSpd * dpr / 1000,
      dmg: w.dmg,
      born: now
    });
  }

  function update(dt){
    const now = performance.now();
    finishReloadIfReady(now);

    // move player
    const spd = (player.spd * dpr) * (dt/1000);
    player.x = clamp(player.x + joyVX*spd, player.r, W-player.r);
    player.y = clamp(player.y + joyVY*spd, player.r, H-player.r);

    // bullets
    for (const b of bullets){
      b.x += b.vx * dt;
      b.y += b.vy * dt;
    }
    bullets = bullets.filter(b => (now - b.born) < 900 && b.x>-40*dpr && b.x<W+40*dpr && b.y>-40*dpr && b.y<H+40*dpr);

    // zombies chase
    for (const z of zombies){
      const dx = player.x - z.x;
      const dy = player.y - z.y;
      const len = Math.sqrt(dx*dx+dy*dy) || 1;
      z.x += (dx/len) * z.spd * (dt/1000);
      z.y += (dy/len) * z.spd * (dt/1000);
      z.hitFlash = Math.max(0, z.hitFlash - dt);
    }

    // bullet hits
    const insta = isInstaKill(now);
    for (const b of bullets){
      for (const z of zombies){
        const rr = (z.r + 3*dpr);
        if (dist2(b.x,b.y,z.x,z.y) <= rr*rr){
          const dmg = insta ? 9999 : b.dmg;
          z.hp -= dmg;
          z.hitFlash = 120;
          // kill bullet on hit
          b.born = -999999; // mark
          break;
        }
      }
    }
    bullets = bullets.filter(b => b.born > 0);

    // zombie touch damage
    for (const z of zombies){
      const rr = (z.r + player.r);
      if (dist2(player.x, player.y, z.x, z.y) <= rr*rr){
        // continuous damage
        player.hp -= (z.dmg * diffK()) * (dt/1000) * 10;
        if (player.hp <= 0){
          player.hp = 0;
          gameOver();
          return;
        }
      }
    }

    // remove dead zombies, reward coins
    let alive = [];
    for (const z of zombies){
      if (z.hp > 0) { alive.push(z); continue; }
      waveKills++;
      killCount++;
      const baseCoins = (z.kind==="tank") ? 120 : (z.kind==="fast") ? 60 : 40;
      player.coins += Math.round(baseCoins * powerupMul(now));
      maybeDropPowerup(z.x, z.y);
    }
    zombies = alive;

    // powerups
    powerups = powerups.filter(pu => (now - pu.born) < pu.ttl);
    for (let i=powerups.length-1;i>=0;i--){
      const pu = powerups[i];
      const rr = (pu.r + player.r);
      if (dist2(player.x, player.y, pu.x, pu.y) <= rr*rr){
        collectPowerup(pu);
        powerups.splice(i,1);
      }
    }

    // wave progression
    if (waveKills >= waveTargetKills && zombies.length === 0){
      wave++;
      // small heal between waves (элитно, но не имба)
      player.hp = Math.min(player.maxHp, player.hp + 18);
      spawnWave();
    }

    // auto-fire if button held
    if (fireActive){
      shootToward(player.aimX, player.aimY);
    }

    setHUD();
  }

  function draw(){
    ctx.clearRect(0,0,W,H);

    // background grid
    ctx.globalAlpha = 0.12;
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = 1*dpr;
    const step = 50*dpr;
    for(let x=0; x<=W; x+=step){ ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke(); }
    for(let y=0; y<=H; y+=step){ ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke(); }
    ctx.globalAlpha = 1;

    // arena vignette
    const g = ctx.createRadialGradient(W*0.5,H*0.5, 10*dpr, W*0.5,H*0.5, Math.max(W,H)*0.6);
    g.addColorStop(0, "rgba(124,92,255,.06)");
    g.addColorStop(1, "rgba(0,0,0,.18)");
    ctx.fillStyle = g;
    ctx.fillRect(0,0,W,H);

    // bullets
    ctx.fillStyle = "rgba(255,255,255,.92)";
    for (const b of bullets){
      ctx.beginPath();
      ctx.arc(b.x,b.y, 2.4*dpr, 0, Math.PI*2);
      ctx.fill();
    }

    // powerups
    for (const pu of powerups){
      ctx.save();
      ctx.translate(pu.x, pu.y);
      ctx.globalAlpha = 0.95;
      if (pu.type==="double_points") ctx.strokeStyle = "rgba(255,176,32,.95)";
      if (pu.type==="insta_kill") ctx.strokeStyle = "rgba(255,77,109,.95)";
      if (pu.type==="max_ammo") ctx.strokeStyle = "rgba(24,209,163,.95)";
      ctx.lineWidth = 4*dpr;
      ctx.beginPath();
      ctx.arc(0,0,pu.r,0,Math.PI*2);
      ctx.stroke();
      ctx.globalAlpha = 0.55;
      ctx.beginPath();
      ctx.arc(0,0,pu.r*0.6,0,Math.PI*2);
      ctx.stroke();
      ctx.restore();
    }

    // zombies
    for (const z of zombies){
      ctx.save();
      ctx.translate(z.x, z.y);

      // body
      const base = (z.kind==="tank") ? "rgba(255,77,109,.28)" : (z.kind==="fast") ? "rgba(255,176,32,.22)" : "rgba(124,92,255,.18)";
      ctx.fillStyle = base;
      ctx.beginPath(); ctx.arc(0,0,z.r,0,Math.PI*2); ctx.fill();

      // outline
      ctx.strokeStyle = (z.hitFlash>0) ? "rgba(255,255,255,.85)" : "rgba(255,255,255,.12)";
      ctx.lineWidth = (z.kind==="tank") ? 4*dpr : 3*dpr;
      ctx.beginPath(); ctx.arc(0,0,z.r,0,Math.PI*2); ctx.stroke();

      // hp bar
      const w = z.r*2.0;
      ctx.globalAlpha = 0.85;
      ctx.strokeStyle = "rgba(255,255,255,.16)";
      ctx.lineWidth = 4*dpr;
      ctx.beginPath(); ctx.moveTo(-w*0.55, -z.r-10*dpr); ctx.lineTo(w*0.55, -z.r-10*dpr); ctx.stroke();

      ctx.strokeStyle = "rgba(24,209,163,.90)";
      const hpRatio = clamp(z.hp / (100 + wave*10), 0, 1);
      ctx.beginPath(); ctx.moveTo(-w*0.55, -z.r-10*dpr); ctx.lineTo(-w*0.55 + (w*1.1)*hpRatio, -z.r-10*dpr); ctx.stroke();

      ctx.restore();
    }

    // player
    ctx.save();
    ctx.translate(player.x, player.y);

    // crown glow ring
    ctx.globalAlpha = 0.95;
    ctx.strokeStyle = "rgba(24,209,163,.75)";
    ctx.lineWidth = 5*dpr;
    ctx.beginPath(); ctx.arc(0,0,player.r*1.35,0,Math.PI*2); ctx.stroke();

    // body
    ctx.fillStyle = "rgba(255,255,255,.92)";
    ctx.beginPath(); ctx.arc(0,0,player.r,0,Math.PI*2); ctx.fill();

    // aim line
    ctx.globalAlpha = 0.65;
    ctx.strokeStyle = "rgba(124,92,255,.85)";
    ctx.lineWidth = 3*dpr;
    ctx.beginPath(); ctx.moveTo(0,0); ctx.lineTo((player.aimX-player.x)*0.25, (player.aimY-player.y)*0.25); ctx.stroke();

    ctx.restore();

    // buffs indicator
    const now = performance.now();
    let y = 18*dpr;
    if (now < doublePointsUntil){
      ctx.fillStyle = "rgba(255,176,32,.95)";
      ctx.font = `${12*dpr}px -apple-system, system-ui, Arial`;
      ctx.fillText("DOUBLE POINTS", 14*dpr, y); y += 16*dpr;
    }
    if (now < instaKillUntil){
      ctx.fillStyle = "rgba(255,77,109,.95)";
      ctx.fillText("INSTA-KILL", 14*dpr, y); y += 16*dpr;
    }

    // mag indicator
    const wpn = currentWeapon();
    ctx.fillStyle = "rgba(255,255,255,.85)";
    ctx.font = `${12*dpr}px -apple-system, system-ui, Arial`;
    ctx.fillText(`${wpn.name} • MAG ${player.mag}/${wpn.mag}`, 14*dpr, H - 16*dpr);
  }

  function loop(now){
    if (!running) return;
    const dt = Math.min(40, now - lastFrame);
    lastFrame = now;
    update(dt);
    draw();
    requestAnimationFrame(loop);
  }

  function sendResult(){
    if (!tg) return;
    const payload = {
      v: 1,
      action: "game_result",
      ts: Date.now(),
      game: "zombies",
      mode: "solo",
      score: Math.round((killCount*45) + (wave*220) + player.coins*0.6),
      wave,
      kills: killCount,
      coins_earned: player.coins,
      loadout: { weapon: player.weaponId, perks: Array.from(player.perks) },
      duration_ms: Math.round(performance.now() - tStart),
      profile,
      initData: tg.initData || null
    };
    tg.sendData(JSON.stringify(payload));

    try{
      tg.MainButton.setText("✅ Send & Close");
      tg.MainButton.show();
      tg.MainButton.onClick(() => tg.close());
    } catch {}
  }

  function gameOver(){
    running = false;
    setStatus(`ТЫ ПАЛ. Волна ${wave}, убийств ${killCount}. Результат улетел ⚡`, "var(--bad)");
    sendResult();
  }

  // --- Shop UI ---
  function openShop(){
    $("shop").style.display = "flex";
    renderShop();
  }
  function closeShop(){
    $("shop").style.display = "none";
  }

  function canBuy(cost){ return player.coins >= cost; }

  function buyItem(item){
    if (!canBuy(item.cost)) return;

    if (item.type === "weapon"){
      player.coins -= item.cost;
      player.weaponId = item.id;
      const w = currentWeapon();
      player.mag = w.mag;
      player.reloading = false;
      setStatus(`Купил оружие: ${w.name} 👑`, "var(--ok)");
    }

    if (item.type === "perk"){
      if (player.perks.has(item.id)) return;
      player.coins -= item.cost;
      player.perks.add(item.id);
      const before = player.maxHp;
      const { } = applyPerks();
      // adjust hp baseline
      const newMax = player.maxHp;
      if (newMax > before) player.hp += (newMax - before);
      player.hp = Math.min(player.maxHp, player.hp);
      setStatus(`Активирован перк: ${perkDefs[item.id].name}`, "var(--ok)");
    }

    if (item.type === "util"){
      if (item.id === "ammo"){
        player.coins -= item.cost;
        const w = currentWeapon();
        player.mag = w.mag;
        player.reloading = false;
        setStatus("Ammo refilled ⚡", "var(--ok)");
      }
    }

    setHUD();
    renderShop();
  }

  function renderShop(){
    $("shopCoins").textContent = String(player.coins);
    const grid = $("shopGrid");
    grid.innerHTML = "";

    for (const item of shopItems){
      const row = document.createElement("div");
      row.className = "item";

      const meta = document.createElement("div");
      meta.className = "meta";
      const t = document.createElement("b");
      t.textContent = `${item.title} — ${item.cost}c`;
      const s = document.createElement("small");
      s.textContent = item.sub;
      meta.appendChild(t);
      meta.appendChild(s);

      const btn = document.createElement("button");
      btn.className = "buy";
      btn.textContent = "BUY";
      btn.disabled = !canBuy(item.cost);

      // owned states
      if (item.type === "perk" && player.perks.has(item.id)){
        btn.textContent = "OWNED";
        btn.disabled = true;
      }
      if (item.type === "weapon" && player.weaponId === item.id){
        btn.textContent = "EQUIPPED";
        btn.disabled = true;
      }

      btn.addEventListener("click", () => buyItem(item));

      row.appendChild(meta);
      row.appendChild(btn);
      grid.appendChild(row);
    }
  }

  // --- Controls: joystick + aiming ---
  function joyStart(e){
    const p = getPoint(e);
    joyActive = true;
    joyId = p.id;
    const baseRect = $("joyBase").getBoundingClientRect();
    joyCX = (baseRect.left + baseRect.width/2);
    joyCY = (baseRect.top + baseRect.height/2);
    moveStick(p.x, p.y);
  }

  function joyMove(e){
    if (!joyActive) return;
    const p = getPoint(e, joyId);
    if (!p) return;
    moveStick(p.x, p.y);
  }

  function joyEnd(e){
    joyActive = false; joyId = null;
    joyVX = 0; joyVY = 0;
    $("joyStick").style.transform = `translate(0px,0px)`;
  }

  function moveStick(x, y){
    const dx = x - joyCX;
    const dy = y - joyCY;
    const max = 44; // css px
    const len = Math.sqrt(dx*dx+dy*dy) || 1;
    const nx = (len > max) ? dx/len*max : dx;
    const ny = (len > max) ? dy/len*max : dy;
    $("joyStick").style.transform = `translate(${nx}px,${ny}px)`;
    joyVX = clamp(nx / max, -1, 1);
    joyVY = clamp(ny / max, -1, 1);
  }

  function getPoint(e, preferId=null){
    // pointer events preferred
    if (e.pointerId != null){
      return { id: e.pointerId, x: e.clientX, y: e.clientY };
    }
    // touch fallback
    const t = e.touches || e.changedTouches;
    if (!t || !t.length) return null;
    if (preferId == null) return { id: 0, x: t[0].clientX, y: t[0].clientY };
    for (const ti of t){
      if (ti.identifier === preferId) return { id: preferId, x: ti.clientX, y: ti.clientY };
    }
    return null;
  }

  function setAimFromClient(x,y){
    const rect = canvas.getBoundingClientRect();
    player.aimX = (x - rect.left) * dpr;
    player.aimY = (y - rect.top) * dpr;
  }

  function fireDown(){
    fireActive = true;
    setStatus("FIRE 🔥", "var(--warn)");
  }
  function fireUp(){
    fireActive = false;
    setStatus("Контроль. Магазин/перки — по таймингу 👑", "var(--ok)");
  }

  // allow aim by dragging right side on canvas
  function canvasAim(e){
    const p = getPoint(e);
    if (!p) return;
    setAimFromClient(p.x, p.y);
  }

  function start(){
    running = true;
    tStart = performance.now();
    lastFrame = performance.now();

    // reset state
    zombies = []; bullets = []; powerups = [];
    wave = 1; killCount = 0; player.coins = 0;
    player.weaponId = "pistol";
    player.perks = new Set();
    player.maxHp = 100;
    player.hp = 100;
    player.reloading = false;
    player.mag = currentWeapon().mag;
    doublePointsUntil = 0; instaKillUntil = 0;

    // position
    player.x = W*0.5;
    player.y = H*0.55;
    player.aimX = W*0.5;
    player.aimY = H*0.2;

    setHUD();
    setStatus("Зашёл. Первая волна — разогрев.", "var(--ok)");
    spawnWave();
    requestAnimationFrame(loop);
  }

  function boot(){
    if (tg){
      tg.ready(); tg.expand();
      try { tg.setBackgroundColor?.("#070A12"); } catch {}
      $("modePillText").textContent = profile.voice || "TEAMMATE";
    } else {
      $("modePillText").textContent = profile.voice || "TEAMMATE";
    }

    resize();
    window.addEventListener("resize", resize);

    // joystick events
    const base = $("joyBase");
    base.addEventListener("pointerdown", (e)=>{ base.setPointerCapture?.(e.pointerId); joyStart(e); }, { passive:true });
    base.addEventListener("pointermove", joyMove, { passive:true });
    base.addEventListener("pointerup", joyEnd, { passive:true });
    base.addEventListener("pointercancel", joyEnd, { passive:true });

    // canvas aim
    canvas.addEventListener("pointerdown", (e)=>{ canvasAim(e); }, { passive:true });
    canvas.addEventListener("pointermove", (e)=>{ canvasAim(e); }, { passive:true });

    // buttons
    $("btnShoot").addEventListener("pointerdown", () => fireDown(), { passive:true });
    $("btnShoot").addEventListener("pointerup", () => fireUp(), { passive:true });
    $("btnShoot").addEventListener("pointercancel", () => fireUp(), { passive:true });

    $("btnReload").addEventListener("click", () => reloadNow());
    $("btnShop").addEventListener("click", () => openShop());
    $("shopClose").addEventListener("click", () => closeShop());
    $("shop").addEventListener("click", (e) => { if (e.target === $("shop")) closeShop(); });

    $("btnStart").addEventListener("click", () => { try { tg?.MainButton?.hide(); } catch {} start(); });
    $("btnBack").addEventListener("click", () => location.href = "../index.html");

    $("tabHome").addEventListener("click", () => location.href = "../index.html");
    $("tabAim").addEventListener("click", () => location.href = "../aim/index.html" + "?" + new URLSearchParams(profile).toString());
    $("tabZ").addEventListener("click", () => {});

    setHUD();
    setStatus("Готов. Нажми Start.", "var(--mut)");
  }

  // autoshot tick: keep aiming at last aim point
  setInterval(() => {
    if (!running) return;
    if (!fireActive) return;
    shootToward(player.aimX, player.aimY);
  }, 16);

  document.addEventListener("DOMContentLoaded", boot);
})();
