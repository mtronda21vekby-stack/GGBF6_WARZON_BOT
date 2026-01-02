/* =========================================================
   BLACK CROWN OPS — ZOMBIES vNEXT (CORE SPLIT)
   COPY–PASTE ALL FILES AS-IS
   ========================================================= */

/* =========================================================
   FILE: app/webapp/static/zombies.core.js
   ========================================================= */
(() => {
  "use strict";

  const clamp = (v,a,b)=>Math.max(a,Math.min(b,v));
  const dist2=(ax,ay,bx,by)=>{const dx=ax-bx,dy=ay-by;return dx*dx+dy*dy};

  const WEAPONS = {
    SMG:{dmg:13,rpm:720,speed:980,spread:.09,mag:30,reload:1.35,crit:1.6},
    AR:{dmg:17,rpm:600,speed:1050,spread:.07,mag:30,reload:1.55,crit:1.75},
    Shotgun:{dmg:8,rpm:110,speed:920,spread:.25,mag:6,reload:1.9,crit:1.5,pellets:8}
  };

  const RUN = {
    running:false, mode:"arcade",
    x:0,y:0,r:14,
    hp:100,maxHp:100,
    armor:0,armorMax:150,plates:0,platesMax:3,plateValue:50,
    wave:1,kills:0,coins:0,
    weapon:"SMG",ammo:30,lastShot:0,reloading:false,reloadAt:0,
    zombies:[],bullets:[],
    joyX:0,joyY:0,
    aimX:0,aimY:0,shoot:false,
    w:0,h:0
  };

  function reset(w,h){
    RUN.running=false;
    RUN.x=w*.5; RUN.y=h*.6;
    RUN.hp=RUN.maxHp=100;
    RUN.armor=0; RUN.plates=0;
    RUN.wave=1; RUN.kills=0; RUN.coins=0;
    RUN.weapon="SMG";
    RUN.ammo=WEAPONS.SMG.mag;
    RUN.zombies.length=0;
    RUN.bullets.length=0;
  }

  function spawnZombie(){
    const side=Math.floor(Math.random()*4);
    let x,y;
    if(side===0){x=-40;y=Math.random()*RUN.h}
    if(side===1){x=RUN.w+40;y=Math.random()*RUN.h}
    if(side===2){x=Math.random()*RUN.w;y=-40}
    if(side===3){x=Math.random()*RUN.w;y=RUN.h+40}
    const hp=22+RUN.wave*1.4;
    RUN.zombies.push({x,y,r:16,hp,maxHp:hp,spd:50+RUN.wave});
  }

  function shoot(t){
    const w=WEAPONS[RUN.weapon];
    const dt=60000/(w.rpm);
    if(t-RUN.lastShot<dt||RUN.reloading||RUN.ammo<=0)return;
    RUN.lastShot=t; RUN.ammo--;
    let dx=RUN.aimX-RUN.x,dy=RUN.aimY-RUN.y;
    const len=Math.hypot(dx,dy)||1; dx/=len; dy/=len;
    const ang=Math.atan2(dy,dx);
    const mk=(a)=>{
      RUN.bullets.push({
        x:RUN.x+dx*(RUN.r+10),
        y:RUN.y+dy*(RUN.r+10),
        vx:Math.cos(a)*w.speed,
        vy:Math.sin(a)*w.speed,
        r:2.6,life:1.1,dmg:w.dmg
      });
    };
    if(w.pellets){
      for(let i=0;i<w.pellets;i++)mk(ang+(Math.random()*2-1)*w.spread);
    }else mk(ang+(Math.random()*2-1)*w.spread);
  }

  function tick(dt,t){
    if(!RUN.running)return;
    RUN.x=clamp(RUN.x+RUN.joyX*220*dt,20,RUN.w-20);
    RUN.y=clamp(RUN.y+RUN.joyY*220*dt,90,RUN.h-20);
    if(RUN.shoot)shoot(t);

    if(Math.random()<0.02)spawnZombie();

    for(let i=RUN.bullets.length-1;i>=0;i--){
      const b=RUN.bullets[i];
      b.life-=dt;
      b.x+=b.vx*dt; b.y+=b.vy*dt;
      if(b.life<=0){RUN.bullets.splice(i,1);continue}
      for(let j=RUN.zombies.length-1;j>=0;j--){
        const z=RUN.zombies[j];
        if(dist2(b.x,b.y,z.x,z.y)<(z.r+b.r)**2){
          z.hp-=b.dmg;
          RUN.bullets.splice(i,1);
          if(z.hp<=0){RUN.zombies.splice(j,1);RUN.kills++;RUN.coins++}
          break;
        }
      }
    }

    for(const z of RUN.zombies){
      const dx=RUN.x-z.x,dy=RUN.y-z.y;
      const len=Math.hypot(dx,dy)||1;
      z.x+=dx/len*z.spd*dt;
      z.y+=dy/len*z.spd*dt;
      if(dist2(z.x,z.y,RUN.x,RUN.y)<(z.r+RUN.r)**2){
        RUN.hp-=10*dt;
        if(RUN.hp<=0)RUN.running=false;
      }
    }
  }

  window.BCO_ZOMBIES_CORE={
    RUN,WEAPONS,reset,tick,spawnZombie
  };
})();

/* =========================================================
   FILE: app/webapp/static/zombies.input.js
   ========================================================= */
(() => {
  "use strict";
  const C=window.BCO_ZOMBIES_CORE;
  let joyId=null,shootId=null;
  function p(e){return{ x:e.clientX??e.touches[0].clientX,
                        y:e.clientY??e.touches[0].clientY}}
  function bind(canvas){
    canvas.addEventListener("pointerdown",e=>{
      if(e.clientX<window.innerWidth/2){
        joyId=e.pointerId;
        const s=p(e); C.RUN.joyCX=s.x; C.RUN.joyCY=s.y;
      }else{
        shootId=e.pointerId;
        const s=p(e); C.RUN.aimX=s.x; C.RUN.aimY=s.y; C.RUN.shoot=true;
      }
    });
    window.addEventListener("pointermove",e=>{
      if(e.pointerId===joyId){
        const s=p(e);
        const dx=(s.x-C.RUN.joyCX)/40,dy=(s.y-C.RUN.joyCY)/40;
        C.RUN.joyX=Math.max(-1,Math.min(1,dx));
        C.RUN.joyY=Math.max(-1,Math.min(1,dy));
      }
      if(e.pointerId===shootId){
        const s=p(e); C.RUN.aimX=s.x; C.RUN.aimY=s.y;
      }
    });
    window.addEventListener("pointerup",e=>{
      if(e.pointerId===joyId){joyId=null;C.RUN.joyX=C.RUN.joyY=0}
      if(e.pointerId===shootId){shootId=null;C.RUN.shoot=false}
    });
  }
  window.BCO_ZOMBIES_INPUT={bind};
})();

/* =========================================================
   FILE: app/webapp/static/zombies.render.js
   ========================================================= */
(() => {
  "use strict";
  const C=window.BCO_ZOMBIES_CORE;
  const A=window.BCO_ZOMBIES_ASSETS;

  function draw(ctx){
    const R=C.RUN;
    ctx.clearRect(0,0,R.w,R.h);
    for(const b of R.bullets){
      ctx.fillStyle="#fff";
      ctx.beginPath();ctx.arc(b.x,b.y,b.r,0,Math.PI*2);ctx.fill();
    }
    for(const z of R.zombies){
      A?.drawZombie?.(ctx,z.x,z.y,{scale:.34})||
      (ctx.fillStyle="#3f3",ctx.beginPath(),ctx.arc(z.x,z.y,z.r,0,Math.PI*2),ctx.fill());
    }
    A?.drawPlayer?.(ctx,R.x,R.y,R.joyX,R.joyY,{scale:.34})||
    (ctx.fillStyle="#4af",ctx.beginPath(),ctx.arc(R.x,R.y,R.r,0,Math.PI*2),ctx.fill());
  }
  window.BCO_ZOMBIES_RENDER={draw};
})();

/* =========================================================
   FILE: app/webapp/static/zombies.boot.js
   ========================================================= */
(() => {
  "use strict";
  const CORE=window.BCO_ZOMBIES_CORE;
  const INPUT=window.BCO_ZOMBIES_INPUT;
  const RENDER=window.BCO_ZOMBIES_RENDER;

  let canvas,ctx,last=0;

  function loop(t){
    const dt=Math.min(.033,(t-last)/1000); last=t;
    CORE.tick(dt,performance.now());
    RENDER.draw(ctx);
    requestAnimationFrame(loop);
  }

  function open(){
    if(canvas)return;
    canvas=document.createElement("canvas");
    canvas.style.position="fixed";
    canvas.style.inset="0";
    canvas.style.zIndex="9999";
    document.body.appendChild(canvas);
    ctx=canvas.getContext("2d");
    const resize=()=>{
      canvas.width=innerWidth;
      canvas.height=innerHeight;
      CORE.RUN.w=innerWidth;
      CORE.RUN.h=innerHeight;
      CORE.reset(innerWidth,innerHeight);
    };
    window.addEventListener("resize",resize);
    resize();
    INPUT.bind(canvas);
    CORE.RUN.running=true;
    requestAnimationFrame(loop);
  }

  window.BCO_ZOMBIES={
    open,
    start:open,
    stop:()=>CORE.RUN.running=false
  };
})();
