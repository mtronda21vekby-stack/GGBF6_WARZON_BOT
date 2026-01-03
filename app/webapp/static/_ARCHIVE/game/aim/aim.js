(() => {
  const tg = window.Telegram?.WebApp;
  const $ = (id) => document.getElementById(id);

  const qs = new URLSearchParams(location.search);
  const profile = {
    game: qs.get("game") || "warzone",
    platform: qs.get("platform") || "pc",
    input: qs.get("input") || "kbm",
    difficulty: qs.get("difficulty") || "pro",
    voice: qs.get("voice") || "TEAMMATE",
    role: qs.get("role") || "slayer",
  };

  const canvas = $("c");
  const ctx = canvas.getContext("2d");

  let W=0,H=0, dpr=1;

  function resize(){
    dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    const rect = canvas.getBoundingClientRect();
    W = Math.floor(rect.width * dpr);
    H = Math.floor(rect.height * dpr);
    canvas.width = W; canvas.height = H;
  }

  function rnd(min,max){ return min + Math.random()*(max-min); }

  // Target
  let target = null;
  let running = false;
  let tStart = 0;
  let durationMs = 60000;

  let score = 0;
  let shots = 0;
  let hits = 0;
  let lastSpawnAt = 0;

  function spawnTarget(){
    const r = Math.max(18*dpr, Math.min(W,H) * 0.05);
    const x = rnd(r+14*dpr, W-r-14*dpr);
    const y = rnd(r+14*dpr, H-r-14*dpr);
    target = { x,y,r, born: performance.now(), life: rnd(650, 1050) }; // ms
    lastSpawnAt = performance.now();
  }

  function difficultyK(){
    // normal/pro/demon
    const d = (profile.difficulty || "pro");
    if (d === "normal") return 1.05;
    if (d === "demon") return 0.78;
    return 0.92; // pro
  }

  function setStatus(s, color){
    $("status").textContent = s;
    if (color) $("status").style.color = color;
  }

  function setHUD(){
    $("score").textContent = String(score);
    const acc = shots ? Math.round((hits/shots)*100) : 0;
    $("acc").textContent = `${acc}%`;
  }

  function sendResult(){
    if (!tg) return;
    const payload = {
      v: 1,
      action: "game_result",
      ts: Date.now(),
      game: "aim",
      mode: "flick",
      score,
      shots,
      hits,
      accuracy: shots ? (hits/shots) : 0,
      duration_ms: durationMs,
      profile,
      initData: tg.initData || null
    };
    tg.sendData(JSON.stringify(payload));

    // Элитная кнопка Telegram — добить UX
    try{
      tg.MainButton.setText("✅ Send & Close");
      tg.MainButton.show();
      tg.MainButton.onClick(() => tg.close());
    } catch {}
  }

  function start(){
    running = true;
    score = 0; shots = 0; hits = 0;
    tStart = performance.now();
    setHUD();
    setStatus("Работаем. Не промахивайся 👑", "var(--ok)");
    spawnTarget();
    loop();
  }

  function stop(){
    running = false;
    setStatus("Финиш. Результат улетел боту ⚡", "var(--ok)");
    sendResult();
  }

  function draw(){
    // фон
    ctx.clearRect(0,0,W,H);

    // subtle grid
    ctx.globalAlpha = 0.15;
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = 1*dpr;
    const step = 44*dpr;
    for(let x=0; x<=W; x+=step){
      ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke();
    }
    for(let y=0; y<=H; y+=step){
      ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // target
    if (target){
      const age = performance.now() - target.born;
      const life = target.life * difficultyK();
      const t = Math.max(0, Math.min(1, age / life));
      const pulse = 1 + Math.sin((age/150))*0.03;

      // outer glow
      ctx.save();
      ctx.translate(target.x, target.y);
      ctx.scale(pulse, pulse);

      // ring
      ctx.globalAlpha = 0.95;
      ctx.strokeStyle = "rgba(124,92,255,.95)";
      ctx.lineWidth = 6*dpr;
      ctx.beginPath(); ctx.arc(0,0,target.r,0,Math.PI*2); ctx.stroke();

      // inner ring
      ctx.globalAlpha = 0.85;
      ctx.strokeStyle = "rgba(24,209,163,.90)";
      ctx.lineWidth = 3*dpr;
      ctx.beginPath(); ctx.arc(0,0,target.r*0.55,0,Math.PI*2); ctx.stroke();

      // center
      ctx.globalAlpha = 0.95;
      ctx.fillStyle = "rgba(255,255,255,.92)";
      ctx.beginPath(); ctx.arc(0,0,target.r*0.16,0,Math.PI*2); ctx.fill();

      // timer arc
      ctx.globalAlpha = 0.75;
      ctx.strokeStyle = "rgba(255,77,109,.75)";
      ctx.lineWidth = 4*dpr;
      ctx.beginPath();
      ctx.arc(0,0,target.r*1.12, -Math.PI/2, -Math.PI/2 + (Math.PI*2*(1-t)));
      ctx.stroke();

      ctx.restore();

      if (age > life){
        // timeout — промах по времени
        target = null;
        spawnTarget();
      }
    }
  }

  function loop(){
    if (!running) return;
    const now = performance.now();
    const elapsed = now - tStart;
    const left = Math.max(0, durationMs - elapsed);
    $("timeLeft").textContent = (left/1000).toFixed(1);

    if (left <= 0){
      stop();
      return;
    }
    draw();
    requestAnimationFrame(loop);
  }

  function hitTest(px, py){
    if (!target) return false;
    const dx = px - target.x;
    const dy = py - target.y;
    return (dx*dx + dy*dy) <= (target.r*target.r);
  }

  function onPointer(e){
    if (!running) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) * dpr;
    const y = (e.clientY - rect.top) * dpr;
    shots++;

    if (hitTest(x,y)){
      hits++;
      const age = performance.now() - target.born;
      const k = difficultyK();
      const fastBonus = Math.max(0, Math.round(1200 - age) );
      score += Math.round(150 + fastBonus * 0.25 * (1/k));
      // chain
      target = null;
      spawnTarget();
    } else {
      // penalty
      score = Math.max(0, score - 35);
    }
    setHUD();
  }

  function boot(){
    if (tg){
      tg.ready();
      tg.expand();
      try { tg.setBackgroundColor?.("#070A12"); } catch {}
      $("modePillText").textContent = profile.voice || "TEAMMATE";
    } else {
      $("modePillText").textContent = profile.voice || "TEAMMATE";
    }

    resize();
    window.addEventListener("resize", resize);

    canvas.addEventListener("pointerdown", onPointer, { passive: true });

    $("btnStart").addEventListener("click", () => {
      try { tg?.MainButton?.hide(); } catch {}
      start();
    });

    $("btnBack").addEventListener("click", () => location.href = "../index.html");
    $("tabHome").addEventListener("click", () => location.href = "../index.html");
    $("tabAim").addEventListener("click", () => {});
    $("tabZ").addEventListener("click", () => location.href = "../zombies/index.html" + "?" + new URLSearchParams(profile).toString());

    setHUD();
    setStatus("Готов. Нажми Start.", "var(--mut)");
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
