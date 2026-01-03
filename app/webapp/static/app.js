// app/webapp/static/app.js
(() => {
  "use strict";
  
  // =========================
  // ✅ ВЕРСИЯ И КОНФИГУРАЦИЯ
  // =========================
  const CONFIG = {
    VERSION: "2.0.0",
    STORAGE_KEY: "bco_state_v1",
    CHAT_KEY: "bco_chat_v1",
    BUILD_KEY: "bco_build",
    API_TIMEOUT: 12000,
    CHAT_HISTORY_LIMIT: 80,
    AIM_DURATION: 20000,
    MAX_PAYLOAD_SIZE: 15000,

    // Zombies экономика/квест
    RELIC_DROP_CHANCE: 0.04,
    COINS_PER_KILL: 1,
    COINS_PER_WAVE: 3,

    // ✅ CONTRACT: zoom bump is +0.5 to current (0.5 -> 1.0)
    ZOOM_BUMP: 0.5,

    // ✅ CONTRACT: skins smaller ~1.5x and player faster than zombies (best-effort via engine APIs)
    PLAYER_SCALE: 0.6667,
    PLAYER_SPEED_MULT: 1.18,
    
    // Цены в магазине
    PRICES: {
      upgrade: 8,
      reroll: 4,
      reload: 3,
      Jug: 12,
      Speed: 10,
      Mag: 8,
      Armor: 14
    }
  };

  // =========================
  // ✅ СИНГЛТОНЫ И СОСТОЯНИЕ
  // =========================
  const AppState = {
    tg: window.Telegram?.WebApp || null,
    isInitialized: false,
    isGameActive: false,
    currentTab: "home",
    buildId: window.__BCO_BUILD__ || "dev",
    
    // Основное состояние
    state: {
      // Профиль
      game: "Warzone",
      focus: "aim",
      mode: "Normal",
      platform: "PC",
      input: "Controller",
      voice: "TEAMMATE",
      role: "Flex",
      bf6_class: "Assault",
      
      // Zombies
      zombies_map: "Ashes",
      zombies_mode: "arcade",
      character: "male",
      skin: "default",
      render: "2d",
      
      // Экономика и прогресс
      z_coins: 0,
      z_relics: 0,
      z_wonder_unlocked: false,
      z_wonder_weapon: "CROWN_RAY",
      z_best: { arcade: 0, roguelike: 0 },
      
      // Аккаунт
      acc_xp: 0,
      acc_level: 1,
      z_xp: 0,
      z_level: 1
    },
    
    // Чат
    chat: {
      history: [],
      lastAskAt: 0,
      isTyping: false
    },
    
    // AIM игра
    aim: {
      running: false,
      startedAt: 0,
      shots: 0,
      hits: 0,
      timerId: null,
      durationMs: CONFIG.AIM_DURATION
    },
    
    // Zombies игра
    zombies: {
      active: false,
      overlay: null,
      canvas: null,
      hudPill: null,
      hudPill2: null,
      shop: null,
      modal: null,
      
      // Экономика
      econ: {
        coins: 0,
        lastKills: 0,
        lastWave: 0
      },
      
      // Ввод
      input: {
        move: { x: 0, y: 0 },
        aim: { x: 0, y: 0 },
        firing: false,
        updatedAt: 0
      },
      
      // Джойстики
      joys: {
        left: null,
        right: null
      },

      // FIRE button handlers state
      fire: {
        active: false,
        pointerId: null
      }
    },
    
    // Системные флаги
    flags: {
      noZoomInstalled: false,
      zhudHooked: false,
      tgButtonsWired: false,
      inputPumpActive: false,

      // ✅ hard-hide loop for Telegram buttons during gameplay
      tgHardHideActive: false,
      tgHardHideTimer: null,

      // ✅ apply tuning only once per enter
      zoomBumpedThisEnter: false,
      tuningAppliedThisEnter: false
    }
  };

  // =========================
  // ✅ УТИЛИТЫ И ХЕЛПЕРЫ
  // =========================
  const Utils = {
    // DOM
    qs: (selector) => document.querySelector(selector),
    qsa: (selector) => Array.from(document.querySelectorAll(selector)),
    createElement: (tag, className, innerHTML) => {
      const el = document.createElement(tag);
      if (className) el.className = className;
      if (innerHTML) el.innerHTML = innerHTML;
      return el;
    },
    
    // Время
    now: () => Date.now(),
    formatTime: (timestamp) => {
      try {
        const date = new Date(timestamp);
        return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
      } catch {
        return '';
      }
    },
    
    // Математика
    clamp: (value, min, max) => Math.max(min, Math.min(max, value)),
    clampInt: (value, min, max) => {
      const n = Number.isFinite(+value) ? Math.floor(+value) : min;
      return Utils.clamp(n, min, max);
    },
    length: (x, y) => Math.sqrt(x * x + y * y),
    random: (min, max) => min + Math.random() * (max - min),
    
    // Безопасность
    escapeHtml: (text) => {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    },
    
    safeJsonParse: (str) => {
      try {
        return JSON.parse(str);
      } catch {
        return null;
      }
    },
    
    // Проверки
    isTouchDevice: () => 'ontouchstart' in window || navigator.maxTouchPoints > 0,
    isIOS: () => /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream,
    
    // Логирование
    log: (message, data) => {
      if (AppState.buildId !== 'prod') {
        console.log(`[BCO] ${message}`, data || '');
      }
    },
    
    error: (message, error) => {
      console.error(`[BCO Error] ${message}`, error || '');
    },
    
    // Haptic feedback
    haptic: (type = "impact", style = "medium") => {
      try {
        if (!AppState.tg?.HapticFeedback) return;
        
        switch (type) {
          case "impact":
            AppState.tg.HapticFeedback.impactOccurred(style);
            break;
          case "notification":
            AppState.tg.HapticFeedback.notificationOccurred(style);
            break;
          case "selection":
            AppState.tg.HapticFeedback.selectionChanged();
            break;
        }
      } catch (error) {
        Utils.error("Haptic feedback failed", error);
      }
    },
    
    // Toast уведомления
    toast: (message, duration = 1600) => {
      const toastEl = Utils.qs("#toast");
      if (!toastEl) return;
      
      toastEl.textContent = String(message || "");
      toastEl.classList.add("show");
      
      setTimeout(() => {
        toastEl.classList.remove("show");
      }, duration);
    },
    
    // Throttle для производительности
    throttle: (func, limit) => {
      let inThrottle;
      return function(...args) {
        if (!inThrottle) {
          func.apply(this, args);
          inThrottle = true;
          setTimeout(() => inThrottle = false, limit);
        }
      };
    },
    
    // Debounce
    debounce: (func, wait) => {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          clearTimeout(timeout);
          func.apply(this, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
      };
    }
  };

  // =========================
  // ✅ ОБРАБОТЧИК КАСАНИЙ (Ultra Tap)
  // =========================
  const TouchHandler = {
    init() {
      if (window.__BCO_TOUCH_HANDLER_INIT__) return;
      window.__BCO_TOUCH_HANDLER_INIT__ = true;
      
      this.installNoZoomGuards();
    },
    
    onTap(element, handler, options = {}) {
      if (!element) return;
      
      const lockMs = Math.max(120, options.lockMs || 220);
      let locked = false;
      let lastPointerUpAt = 0;
      
      const lock = () => {
        locked = true;
        setTimeout(() => { locked = false; }, lockMs);
      };
      
      const fire = (event) => {
        if (locked) return;
        lock();
        try {
          handler(event);
        } catch (error) {
          Utils.error("Tap handler error", error);
        }
      };
      
      // Modern Pointer Events
      if (window.PointerEvent) {
        element.style.touchAction = element.style.touchAction || "manipulation";
        
        element.addEventListener("pointerdown", (e) => {
          if (typeof e.button === "number" && e.button !== 0) return;
          try {
            element.setPointerCapture?.(e.pointerId);
          } catch {}
        }, { capture: true, passive: true });
        
        element.addEventListener("pointerup", (e) => {
          if (typeof e.button === "number" && e.button !== 0) return;
          lastPointerUpAt = Utils.now();
          fire(e);
        }, { capture: true, passive: true });
        
        element.addEventListener("click", (e) => {
          if (Utils.now() - lastPointerUpAt < 380) return;
          fire(e);
        }, { capture: true, passive: true });
        
        return;
      }
      
      // Fallback для старых устройств
      element.addEventListener("touchstart", (e) => {
        try { e.preventDefault?.(); } catch {}
      }, { capture: true, passive: false });
      
      element.addEventListener("touchend", (e) => {
        try { e.preventDefault?.(); } catch {}
        fire(e);
      }, { capture: true, passive: false });
      
      element.addEventListener("click", (e) => fire(e), { capture: true, passive: true });
    },
    
    installNoZoomGuards() {
      if (AppState.flags.noZoomInstalled) return;
      AppState.flags.noZoomInstalled = true;
      
      let lastTouchEnd = 0;
      
      // Блокировка жестов масштабирования
      const blockGesture = (e) => {
        if (!AppState.isGameActive) return;
        try { e.preventDefault?.(); } catch {}
      };
      
      document.addEventListener("gesturestart", blockGesture, { passive: false });
      document.addEventListener("gesturechange", blockGesture, { passive: false });
      document.addEventListener("gestureend", blockGesture, { passive: false });
      
      // Блокировка multi-touch
      document.addEventListener("touchmove", (e) => {
        if (!AppState.isGameActive) return;
        if ((e.touches?.length || 0) > 1) {
          try { e.preventDefault?.(); } catch {}
        }
      }, { passive: false });
      
      // Блокировка double-tap zoom
      document.addEventListener("touchend", (e) => {
        if (!AppState.isGameActive) return;
        const now = Date.now();
        if (now - lastTouchEnd <= 260) {
          try { e.preventDefault?.(); } catch {}
        }
        lastTouchEnd = now;
      }, { passive: false });
    }
  };

  // =========================
  // ✅ ХРАНИЛИЩЕ (Local + Cloud)
  // =========================
  const Storage = {
    async get(key) {
      // Сначала проверяем Telegram Cloud Storage
      if (AppState.tg?.CloudStorage?.getItem) {
        return new Promise((resolve) => {
          AppState.tg.CloudStorage.getItem(key, (err, value) => {
            if (err) {
              Utils.error("Cloud storage get error", err);
              resolve(null);
            } else {
              resolve(value || null);
            }
          });
        });
      }
      return localStorage.getItem(key);
    },
    
    async set(key, value) {
      // Сначала в Telegram Cloud
      if (AppState.tg?.CloudStorage?.setItem) {
        return new Promise((resolve) => {
          AppState.tg.CloudStorage.setItem(key, value, (err) => {
            if (err) {
              Utils.error("Cloud storage set error", err);
              resolve(false);
            } else {
              resolve(true);
            }
          });
        });
      }
      
      // Fallback на localStorage
      try {
        localStorage.setItem(key, value);
        return true;
      } catch (error) {
        Utils.error("Local storage set error", error);
        return false;
      }
    },
    
    async loadState() {
      try {
        // Загрузка из облака
        const cloudData = await this.get(CONFIG.STORAGE_KEY);
        const parsedCloud = Utils.safeJsonParse(cloudData);
        
        if (parsedCloud && typeof parsedCloud === 'object') {
          const defaults = this.getDefaults();
          AppState.state = { ...defaults, ...parsedCloud };
          this.validateState();
          Utils.log("State loaded from cloud");
          return "cloud";
        }
        
        // Загрузка из localStorage
        const localData = localStorage.getItem(CONFIG.STORAGE_KEY);
        const parsedLocal = Utils.safeJsonParse(localData);
        
        if (parsedLocal && typeof parsedLocal === 'object') {
          const defaults = this.getDefaults();
          AppState.state = { ...defaults, ...parsedLocal };
          this.validateState();
          Utils.log("State loaded from localStorage");
          return "local";
        }
        
        // Дефолтные значения
        AppState.state = this.getDefaults();
        Utils.log("State loaded from defaults");
        return "default";
        
      } catch (error) {
        Utils.error("Failed to load state", error);
        AppState.state = this.getDefaults();
        return "error";
      }
    },
    
    async saveState() {
      try {
        this.validateState();
        const payload = JSON.stringify(AppState.state);
        
        // Сохраняем везде
        localStorage.setItem(CONFIG.STORAGE_KEY, payload);
        await this.set(CONFIG.STORAGE_KEY, payload);
        
        Utils.log("State saved");
        return true;
      } catch (error) {
        Utils.error("Failed to save state", error);
        return false;
      }
    },
    
    async loadChat() {
      try {
        const chatData = await this.get(CONFIG.CHAT_KEY);
        const parsed = Utils.safeJsonParse(chatData);
        
        if (parsed && Array.isArray(parsed.history)) {
          AppState.chat.history = parsed.history.slice(-CONFIG.CHAT_HISTORY_LIMIT);
          Utils.log("Chat loaded");
          return true;
        }
        
        AppState.chat.history = [];
        return true;
      } catch (error) {
        Utils.error("Failed to load chat", error);
        AppState.chat.history = [];
        return false;
      }
    },
    
    async saveChat() {
      try {
        const payload = JSON.stringify({
          history: AppState.chat.history.slice(-120),
          timestamp: Utils.now()
        });
        
        localStorage.setItem(CONFIG.CHAT_KEY, payload);
        await this.set(CONFIG.CHAT_KEY, payload);
        
        return true;
      } catch (error) {
        Utils.error("Failed to save chat", error);
        return false;
      }
    },
    
    getDefaults() {
      return {
        game: "Warzone",
        focus: "aim",
        mode: "Normal",
        platform: "PC",
        input: "Controller",
        voice: "TEAMMATE",
        role: "Flex",
        bf6_class: "Assault",
        zombies_map: "Ashes",
        character: "male",
        skin: "default",
        zombies_mode: "arcade",
        render: "2d",
        z_coins: 0,
        z_relics: 0,
        z_wonder_unlocked: false,
        z_wonder_weapon: "CROWN_RAY",
        z_best: { arcade: 0, roguelike: 0 },
        acc_xp: 0,
        acc_level: 1,
        z_xp: 0,
        z_level: 1
      };
    },
    
    validateState() {
      const s = AppState.state;
      
      // Валидация числовых значений
      s.z_relics = Utils.clampInt(s.z_relics, 0, 5);
      s.z_coins = Utils.clampInt(s.z_coins, 0, 999999);
      s.acc_level = Utils.clampInt(s.acc_level, 1, 999);
      s.z_level = Utils.clampInt(s.z_level, 1, 999);
      
      // Валидация строковых значений
      const validModes = ["arcade", "roguelike"];
      if (!validModes.includes(s.zombies_mode)) s.zombies_mode = "arcade";
      
      const validCharacters = ["male", "female"];
      if (!validCharacters.includes(s.character)) s.character = "male";
      
      const validRender = ["2d", "3d"];
      if (!validRender.includes(s.render)) s.render = "2d";
    },
    
    // Экспорт данных
    exportData() {
      return {
        state: AppState.state,
        chat: {
          historyCount: AppState.chat.history.length,
          lastMessage: AppState.chat.history[AppState.chat.history.length - 1]
        },
        timestamp: Utils.now(),
        version: CONFIG.VERSION
      };
    }
  };

  // =========================
  // ✅ ТЕМА И TELEGRAM API
  // =========================
  const ThemeManager = {
    init() {
      if (!AppState.tg) return;
      this.applyTheme();
      this.setupEventListeners();
    },
    
    applyTheme() {
      try {
        const params = AppState.tg.themeParams || {};
        const root = document.documentElement;
        
        const themeMap = {
          "--tg-bg": params.bg_color,
          "--tg-text": params.text_color,
          "--tg-hint": params.hint_color,
          "--tg-link": params.link_color,
          "--tg-btn": params.button_color,
          "--tg-btn-text": params.button_text_color,
          "--tg-secondary-bg": params.secondary_bg_color
        };
        
        Object.entries(themeMap).forEach(([key, value]) => {
          if (value) root.style.setProperty(key, value);
        });
        
        AppState.tg.setBackgroundColor?.(params.bg_color || "#07070b");
        AppState.tg.setHeaderColor?.(params.secondary_bg_color || params.bg_color || "#07070b");
        
        const dbgTheme = Utils.qs("#dbgTheme");
        if (dbgTheme) dbgTheme.textContent = AppState.tg.colorScheme || "—";
        
      } catch (error) {
        Utils.error("Failed to apply theme", error);
      }
    },
    
    setupEventListeners() {
      if (!AppState.tg) return;
      try {
        AppState.tg.onEvent("themeChanged", () => this.applyTheme());
      } catch (error) {
        Utils.error("Failed to setup theme listener", error);
      }
    },
    
    getThemeInfo() {
      if (!AppState.tg) return null;
      return {
        colorScheme: AppState.tg.colorScheme,
        themeParams: AppState.tg.themeParams,
        platform: AppState.tg.platform,
        viewportHeight: AppState.tg.viewportHeight,
        viewportStableHeight: AppState.tg.viewportStableHeight
      };
    }
  };

  // =========================
  // ✅ UI МЕНЕДЖЕР
  // =========================
  const UIManager = {
    init() {
      this.wireNavigation();
      this.wireSegments();
      this.wireButtons();
      this.updateChips();
      this.wireHeaderChips();
      this.updateTelegramButtons();
    },
    
    wireNavigation() {
      const navButtons = Utils.qsa(".nav-btn, .tab");
      navButtons.forEach(button => {
        TouchHandler.onTap(button, () => {
          Utils.haptic("impact", "light");
          this.selectTab(button.dataset.tab || "home");
        });
      });
    },
    
    selectTab(tab) {
      if (tab === "zombies") tab = "game";
      AppState.currentTab = tab;
      
      Utils.qsa(".nav-btn").forEach(btn => {
        const isActive = btn.dataset.tab === tab;
        btn.classList.toggle("active", isActive);
        btn.setAttribute("aria-selected", isActive ? "true" : "false");
      });
      
      Utils.qsa(".tab").forEach(t => {
        t.classList.toggle("active", t.dataset.tab === tab);
      });
      
      Utils.qsa(".tabpane").forEach(pane => {
        pane.classList.toggle("active", pane.id === `tab-${tab}`);
      });
      
      this.updateTelegramButtons();
      
      try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch {}
      Utils.log(`Tab switched to: ${tab}`);
    },
    
    wireSegments() {
      const segments = [
        { id: "#segGame", prop: "game" },
        { id: "#segFocus", prop: "focus" },
        { id: "#segMode", prop: "mode" },
        { id: "#segPlatform", prop: "platform" },
        { id: "#segInput", prop: "input" },
        { id: "#segVoice", prop: "voice" },
        { id: "#segZMap", prop: "zombies_map" }
      ];
      
      segments.forEach(segment => {
        const root = Utils.qs(segment.id);
        if (!root) return;
        
        TouchHandler.onTap(root, (e) => {
          const button = e.target.closest(".seg-btn");
          if (!button) return;
          
          Utils.haptic("impact", "light");
          AppState.state[segment.prop] = button.dataset.value;
          
          this.setActiveSegment(segment.id, button.dataset.value);
          this.updateChips();
          
          Storage.saveState().then(() => Utils.toast("Сохранено ✅"));
        }, { lockMs: 120 });
      });
      
      this.setActiveSegment("#segPlatform", AppState.state.platform);
      this.setActiveSegment("#segInput", AppState.state.input);
      this.setActiveSegment("#segVoice", AppState.state.voice);
      this.setActiveSegment("#segMode", AppState.state.mode);
      this.setActiveSegment("#segZMap", AppState.state.zombies_map);
      this.setActiveSegment("#segGame", AppState.state.game);
      this.setActiveSegment("#segFocus", AppState.state.focus);
    },
    
    setActiveSegment(rootId, value) {
      const root = Utils.qs(rootId);
      if (!root) return;
      
      root.querySelectorAll(".seg-btn").forEach(button => {
        const isActive = button.dataset.value === value;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
    },
    
    updateChips() {
      const state = AppState.state;
      
      const chipVoice = Utils.qs("#chipVoice");
      if (chipVoice) chipVoice.textContent = state.voice === "COACH" ? "📚 Коуч" : "🤝 Тиммейт";
      
      const chipMode = Utils.qs("#chipMode");
      if (chipMode) {
        let modeText = "🧠 Normal";
        if (state.mode === "Pro") modeText = "🔥 Pro";
        if (state.mode === "Demon") modeText = "😈 Demon";
        chipMode.textContent = modeText;
      }
      
      const chipPlatform = Utils.qs("#chipPlatform");
      if (chipPlatform) {
        let platformText = "🖥 PC";
        if (state.platform === "PlayStation") platformText = "🎮 PlayStation";
        if (state.platform === "Xbox") platformText = "🎮 Xbox";
        chipPlatform.textContent = platformText;
      }
      
      const pillRole = Utils.qs("#pillRole");
      if (pillRole) pillRole.textContent = `🎭 Role: ${state.role}`;
      
      const pillBf6 = Utils.qs("#pillBf6");
      if (pillBf6) pillBf6.textContent = `🟩 Class: ${state.bf6_class}`;
      
      const chatSub = Utils.qs("#chatSub");
      if (chatSub) chatSub.textContent = `${state.voice} • ${state.mode} • ${state.platform}`;
    },
    
    wireHeaderChips() {
      const chipVoice = Utils.qs("#chipVoice");
      const chipMode = Utils.qs("#chipMode");
      const chipPlatform = Utils.qs("#chipPlatform");
      
      TouchHandler.onTap(chipVoice, async () => {
        Utils.haptic("impact", "light");
        AppState.state.voice = AppState.state.voice === "COACH" ? "TEAMMATE" : "COACH";
        this.updateChips();
        this.setActiveSegment("#segVoice", AppState.state.voice);
        await Storage.saveState();
        Utils.toast(AppState.state.voice === "COACH" ? "Коуч включён 📚" : "Тиммейт 🤝");
      });
      
      TouchHandler.onTap(chipMode, async () => {
        Utils.haptic("impact", "light");
        const modes = ["Normal", "Pro", "Demon"];
        const currentIndex = modes.indexOf(AppState.state.mode);
        AppState.state.mode = modes[(currentIndex + 1) % modes.length];
        this.updateChips();
        this.setActiveSegment("#segMode", AppState.state.mode);
        await Storage.saveState();
        Utils.toast(`Режим: ${AppState.state.mode}`);
      });
      
      TouchHandler.onTap(chipPlatform, async () => {
        Utils.haptic("impact", "light");
        const platforms = ["PC", "PlayStation", "Xbox"];
        const currentIndex = platforms.indexOf(AppState.state.platform);
        AppState.state.platform = platforms[(currentIndex + 1) % platforms.length];
        this.updateChips();
        this.setActiveSegment("#segPlatform", AppState.state.platform);
        await Storage.saveState();
        Utils.toast(`Platform: ${AppState.state.platform}`);
      });
    },
    
    wireButtons() {
      this.wireGeneralButtons();
      this.wireChatButtons();
      this.wireAimButtons();
      this.wireZombiesButtons();
    },
    
    wireGeneralButtons() {
      TouchHandler.onTap(Utils.qs("#btnClose"), () => {
        Utils.haptic("impact", "medium");
        AppState.tg?.close?.();
      });
      
      TouchHandler.onTap(Utils.qs("#btnShare"), () => {
        const text = `BLACK CROWN OPS 😈\nТренировки, VOD, настройки, Zombies — всё в одном месте.\nMini App + Fullscreen Zombies (dual-stick).`;
        this.copyToClipboard(text);
      });
      
      TouchHandler.onTap(Utils.qs("#btnBuyMonth"), () => {
        this.sendToBot({ type: "pay", plan: "premium_month", profile: true });
      });
      
      TouchHandler.onTap(Utils.qs("#btnBuyLife"), () => {
        this.sendToBot({ type: "pay", plan: "premium_lifetime", profile: true });
      });
      
      TouchHandler.onTap(Utils.qs("#btnOpenBot"), () => this.openBotMenuHint("main"));
      TouchHandler.onTap(Utils.qs("#btnPremium"), () => this.openBotMenuHint("premium"));
      TouchHandler.onTap(Utils.qs("#btnSync"), () => {
        this.sendToBot({ type: "sync_request", profile: true });
      });
    },
    
    wireChatButtons() {
      TouchHandler.onTap(Utils.qs("#btnChatSend"), () => ChatManager.sendMessage());
      
      TouchHandler.onTap(Utils.qs("#btnChatClear"), async () => {
        Utils.haptic("impact", "light");
        if (confirm("Очистить историю чата?")) {
          AppState.chat.history = [];
          await Storage.saveChat();
          ChatManager.render();
          Utils.toast("Чат очищен ✅");
        }
      });
      
      TouchHandler.onTap(Utils.qs("#btnChatExport"), () => {
        Utils.haptic("impact", "light");
        const text = ChatManager.exportHistory();
        this.copyToClipboard(text || "— пусто —");
      });
      
      const chatInput = Utils.qs("#chatInput");
      if (chatInput) {
        chatInput.addEventListener("keydown", (e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            ChatManager.sendMessage();
          }
        }, { passive: false });
      }
    },
    
    wireAimButtons() {
      const { btnStart, btnStop, btnSend } = AimGame.getElements();
      TouchHandler.onTap(btnStart, () => AimGame.start());
      TouchHandler.onTap(btnStop, () => AimGame.stop());
      TouchHandler.onTap(btnSend, () => AimGame.sendResult());
    },
    
    wireZombiesButtons() {
      TouchHandler.onTap(Utils.qs("#btnZQuickPlay"), () => ZombiesGame.enter());
      TouchHandler.onTap(Utils.qs("#btnPlayZombies"), () => {
        UIManager.selectTab("game");
        ZombiesGame.enter();
      });
      
      TouchHandler.onTap(Utils.qs("#btnZModeArcade"), () => {
        ZombiesGame.setMode("arcade");
        Utils.toast("Zombies: Arcade 💥");
      });
      
      TouchHandler.onTap(Utils.qs("#btnZModeRogue"), () => {
        ZombiesGame.setMode("roguelike");
        Utils.toast("Zombies: Roguelike 😈");
      });
      
      TouchHandler.onTap(Utils.qs("#btnZGameSend"), () => ZombiesGame.sendResult("manual"));
      TouchHandler.onTap(Utils.qs("#btnZGameSend2"), () => ZombiesGame.sendResult("manual"));
      
      TouchHandler.onTap(Utils.qs("#btnZBuyJug"), () => ZombiesGame.buyPerk("Jug"));
      TouchHandler.onTap(Utils.qs("#btnZBuySpeed"), () => ZombiesGame.buyPerk("Speed"));
      TouchHandler.onTap(Utils.qs("#btnZBuyAmmo"), () => ZombiesGame.buyPerk("Mag"));
    },
    
    copyToClipboard(text) {
      try {
        navigator.clipboard.writeText(text).then(() => {
          Utils.toast("Скопировано ✅");
        }).catch(() => {
          const textarea = document.createElement("textarea");
          textarea.value = text;
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand("copy");
          document.body.removeChild(textarea);
          Utils.toast("Скопировано ✅");
        });
      } catch {
        alert(text);
      }
    },
    
    openBotMenuHint(target) {
      this.sendToBot({ type: "nav", target, profile: true });
    },
    
    sendToBot(payload) {
      try {
        BotIntegration.sendData(payload);
      } catch (error) {
        Utils.error("Failed to send to bot", error);
        Utils.haptic("notification", "error");
        Utils.toast("Ошибка отправки");
      }
    },
    
    updateTelegramButtons() {
      if (!AppState.tg) return;
      
      // В режиме игры — жёстко прячем всё
      if (AppState.isGameActive) {
        try { AppState.tg.MainButton.hide(); } catch {}
        try { AppState.tg.BackButton.hide(); } catch {}
        return;
      }
      
      // Back button
      try {
        if (AppState.currentTab !== "home") AppState.tg.BackButton.show();
        else AppState.tg.BackButton.hide();
      } catch {}
      
      // Main button
      try {
        let buttonText = "💎 Premium";
        switch (AppState.currentTab) {
          case "settings": buttonText = "✅ Применить профиль"; break;
          case "coach": buttonText = "🎯 План тренировки"; break;
          case "vod": buttonText = "🎬 Отправить VOD"; break;
          case "game": buttonText = "🧟 Start Fullscreen"; break;
        }
        
        AppState.tg.MainButton.setParams({
          is_visible: true,
          text: buttonText,
          color: AppState.tg.themeParams?.button_color,
          text_color: AppState.tg.themeParams?.button_text_color
        });
        
        if (!AppState.flags.tgButtonsWired) {
          this.wireTelegramButtons();
          AppState.flags.tgButtonsWired = true;
        }
        
      } catch (error) {
        Utils.error("Failed to update Telegram buttons", error);
      }
    },
    
    wireTelegramButtons() {
      if (!AppState.tg) return;
      
      AppState.tg.MainButton.onClick(() => {
        Utils.haptic("impact", "medium");
        
        switch (AppState.currentTab) {
          case "settings":
            this.sendToBot({ type: "set_profile", profile: true });
            break;
          case "coach":
            this.sendToBot({ type: "training_plan", focus: AppState.state.focus, profile: true });
            break;
          case "vod": {
            const t1 = (Utils.qs("#vod1")?.value || "").trim();
            const t2 = (Utils.qs("#vod2")?.value || "").trim();
            const t3 = (Utils.qs("#vod3")?.value || "").trim();
            const note = (Utils.qs("#vodNote")?.value || "").trim();
            this.sendToBot({ type: "vod", times: [t1, t2, t3].filter(Boolean), note, profile: true });
            break;
          }
          case "game":
            ZombiesGame.enter();
            break;
          default:
            this.openBotMenuHint("premium");
        }
      });
      
      AppState.tg.BackButton.onClick(() => {
        Utils.haptic("impact", "light");
        this.selectTab("home");
      });
    }
  };

  // =========================
  // ✅ ИНТЕГРАЦИЯ С БОТОМ
  // =========================
  const BotIntegration = {
    getProfile() {
      return {
        game: AppState.state.game,
        platform: AppState.state.platform,
        input: AppState.state.input,
        difficulty: AppState.state.mode,
        voice: AppState.state.voice,
        role: AppState.state.role,
        bf6_class: AppState.state.bf6_class,
        zombies_map: AppState.state.zombies_map,
        mode: AppState.state.mode
      };
    },
    
    enrichPayload(payload) {
      const initUnsafe = AppState.tg?.initDataUnsafe || {};
      return {
        v: CONFIG.VERSION,
        t: Utils.now(),
        meta: {
          user_id: initUnsafe?.user?.id ?? null,
          chat_id: initUnsafe?.chat?.id ?? null,
          platform: AppState.tg?.platform ?? null,
          build: AppState.buildId,
          viewport: {
            height: AppState.tg?.viewportHeight,
            stable: AppState.tg?.viewportStableHeight
          }
        },
        ...payload
      };
    },
    
    sendData(payload) {
      try {
        const data = { ...payload };
        if (data.profile === true) data.profile = this.getProfile();
        
        const enriched = this.enrichPayload(data);
        let jsonString = JSON.stringify(enriched);
        
        if (jsonString.length > CONFIG.MAX_PAYLOAD_SIZE) {
          Utils.log("Payload too large, trimming");
          if (typeof enriched.text === "string") enriched.text = enriched.text.substring(0, 4000);
          if (typeof enriched.note === "string") enriched.note = enriched.note.substring(0, 4000);
          jsonString = JSON.stringify(enriched).substring(0, CONFIG.MAX_PAYLOAD_SIZE);
        }
        
        if (!AppState.tg?.sendData) throw new Error("Telegram sendData not available");
        AppState.tg.sendData(jsonString);
        
        Utils.haptic("notification", "success");
        Utils.toast("Отправлено в бота 🚀");
        
        const statSession = Utils.qs("#statSession");
        if (statSession) statSession.textContent = "SENT";
        
        return true;
        
      } catch (error) {
        Utils.error("Failed to send data to bot", error);
        Utils.haptic("notification", "error");
        Utils.toast(AppState.tg ? "Ошибка отправки" : "Открой Mini App внутри Telegram");
        return false;
      }
    },
    
    async sendViaAPI(endpoint, data) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.API_TIMEOUT);
        
        const response = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Telegram-Init-Data": AppState.tg?.initData || ""
          },
          body: JSON.stringify(data),
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        return await response.json();
        
      } catch (error) {
        Utils.error("API request failed", error);
        throw error;
      }
    }
  };

  // =========================
  // ✅ ЧАТ МЕНЕДЖЕР
  // =========================
  const ChatManager = {
    init() { this.render(); },
    getLogElement() { return Utils.qs("#chatLog"); },
    
    render() {
      const container = this.getLogElement();
      if (!container) return;
      
      const messages = AppState.chat.history.slice(-CONFIG.CHAT_HISTORY_LIMIT);
      if (messages.length === 0) {
        container.innerHTML = this.getWelcomeMessage();
        return;
      }
      
      let html = "";
      messages.forEach(message => {
        const isBot = message.role === "assistant";
        const sender = isBot ? "BCO" : "Ты";
        const cssClass = isBot ? "bot" : "me";
        const time = Utils.formatTime(message.ts || Utils.now());
        
        html += `
          <div class="chat-row ${cssClass}">
            <div>
              <div class="bubble">${Utils.escapeHtml(message.text)}</div>
              <div class="chat-meta">${sender} • ${time}</div>
            </div>
          </div>
        `;
      });
      
      if (AppState.chat.isTyping) html += this.getTypingIndicator();
      
      container.innerHTML = html;
      setTimeout(() => { container.scrollTop = container.scrollHeight; }, 50);
    },
    
    getWelcomeMessage() {
      const time = Utils.formatTime(Utils.now());
      return `
        <div class="chat-row bot">
          <div>
            <div class="bubble">🤝 Готов. Пиши как есть: где умираешь и что хочешь получить — отвечу тут же. 😈</div>
            <div class="chat-meta">BCO • ${time}</div>
          </div>
        </div>
      `;
    },
    
    getTypingIndicator() {
      return `
        <div class="chat-row bot" id="typing-indicator">
          <div>
            <div class="bubble">
              <span class="typing">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              </span>
            </div>
            <div class="chat-meta">BCO • печатает…</div>
          </div>
        </div>
      `;
    },
    
    setTyping(isTyping) {
      AppState.chat.isTyping = isTyping;
      this.render();
    },
    
    addMessage(role, text) {
      const message = { role, text: String(text || "").trim(), ts: Utils.now() };
      if (!message.text) return;
      
      AppState.chat.history.push(message);
      if (AppState.chat.history.length > 160) AppState.chat.history = AppState.chat.history.slice(-160);
      this.render();
    },
    
    async sendMessage() {
      const input = Utils.qs("#chatInput");
      const text = (input?.value || "").trim();
      
      if (!text) {
        Utils.haptic("notification", "warning");
        Utils.toast("Напиши текст");
        return;
      }
      
      const now = Utils.now();
      if (now - AppState.chat.lastAskAt < 450) {
        Utils.toast("Подождите немного перед следующим сообщением");
        return;
      }
      AppState.chat.lastAskAt = now;
      
      Utils.haptic("impact", "light");
      this.addMessage("user", text);
      
      if (input) {
        input.value = "";
        input.focus();
      }
      
      await Storage.saveChat();
      this.setTyping(true);
      
      try {
        const reply = await this.askBrain(text);
        if (reply) {
          this.addMessage("assistant", reply);
          Utils.haptic("notification", "success");
        } else {
          Utils.haptic("notification", "warning");
          Utils.toast("Нет ответа. Можно отправить в бота.");
        }
      } catch (error) {
        Utils.error("Chat request failed", error);
        this.addMessage("assistant", "Ошибка соединения. Попробуйте позже.");
        Utils.haptic("notification", "error");
      } finally {
        this.setTyping(false);
        await Storage.saveChat();
      }
    },
    
    async askBrain(text) {
      const body = {
        initData: AppState.tg?.initData || "",
        text: String(text || "").trim(),
        profile: BotIntegration.getProfile(),
        history: AppState.chat.history.slice(-20).map(msg => ({ role: msg.role, content: msg.text }))
      };
      
      try {
        const response = await BotIntegration.sendViaAPI("/webapp/api/ask", body);
        if (response?.ok !== true) {
          const error = response?.error || response?.detail || "api_error";
          return `🧠 Mini App: API error (${error}).`;
        }
        return String(response.reply || "");
      } catch (error) {
        const message = error.name === "AbortError" ? "timeout" : (error.message || "network");
        return `🧠 Mini App: network error (${message}).`;
      }
    },
    
    exportHistory() {
      return AppState.chat.history
        .slice(-80)
        .map(msg => {
          const sender = msg.role === "assistant" ? "BCO" : "YOU";
          const time = Utils.formatTime(msg.ts);
          return `[${time}] ${sender}: ${msg.text}`;
        })
        .join("\n");
    }
  };

  // =========================
  // ✅ AIM GAME МЕНЕДЖЕР
  // =========================
  const AimGame = {
    getElements() {
      return {
        arena: Utils.qs("#aimArena"),
        target: Utils.qs("#aimTarget"),
        stat: Utils.qs("#aimStat"),
        btnStart: Utils.qs("#btnAimStart"),
        btnStop: Utils.qs("#btnAimStop"),
        btnSend: Utils.qs("#btnAimSend")
      };
    },
    
    init() { this.reset(); },
    
    reset() {
      AppState.aim.running = false;
      AppState.aim.startedAt = 0;
      AppState.aim.shots = 0;
      AppState.aim.hits = 0;
      
      if (AppState.aim.timerId) {
        clearInterval(AppState.aim.timerId);
        AppState.aim.timerId = null;
      }
      this.updateUI();
    },
    
    moveTarget() {
      const { arena, target } = this.getElements();
      if (!arena || !target) return;
      
      const arenaRect = arena.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      
      const padding = 14;
      const targetWidth = Math.max(30, targetRect.width || 44);
      const targetHeight = Math.max(30, targetRect.height || 44);
      
      const maxX = Math.max(padding, arenaRect.width - padding - targetWidth);
      const maxY = Math.max(padding, arenaRect.height - padding - targetHeight);
      
      const x = padding + Math.random() * (maxX - padding);
      const y = padding + Math.random() * (maxY - padding);
      
      target.style.transform = `translate(${x}px, ${y}px)`;
    },
    
    updateUI() {
      const { stat, btnStart, btnStop, btnSend } = this.getElements();
      
      const accuracy = AppState.aim.shots > 0 
        ? Math.round((AppState.aim.hits / AppState.aim.shots) * 100)
        : 0;
      
      const timeLeft = AppState.aim.running
        ? Math.max(0, AppState.aim.durationMs - (Utils.now() - AppState.aim.startedAt))
        : 0;
      
      if (stat) {
        if (AppState.aim.running) {
          stat.textContent = `⏱ ${(timeLeft / 1000).toFixed(1)}s • 🎯 ${AppState.aim.hits}/${AppState.aim.shots} • Acc ${accuracy}%`;
        } else {
          stat.textContent = `🎯 ${AppState.aim.hits}/${AppState.aim.shots} • Acc ${accuracy}%`;
        }
      }
      
      if (btnStart) btnStart.disabled = AppState.aim.running;
      if (btnStop) btnStop.disabled = !AppState.aim.running;
      if (btnSend) btnSend.disabled = AppState.aim.running || AppState.aim.shots < 5;
    },
    
    start() {
      if (AppState.aim.running) return;
      
      this.reset();
      AppState.aim.running = true;
      AppState.aim.startedAt = Utils.now();
      
      this.moveTarget();
      this.updateUI();
      
      AppState.aim.timerId = setInterval(() => {
        this.moveTarget();
        this.updateUI();
        if (Utils.now() - AppState.aim.startedAt >= AppState.aim.durationMs) this.stop(true);
      }, 650);
      
      Utils.haptic("notification", "success");
      Utils.toast("AIM: поехали 😈");
    },
    
    stop(isAuto = false) {
      if (!AppState.aim.running) return;
      
      AppState.aim.running = false;
      if (AppState.aim.timerId) {
        clearInterval(AppState.aim.timerId);
        AppState.aim.timerId = null;
      }
      this.updateUI();
      
      Utils.haptic("notification", isAuto ? "warning" : "success");
      Utils.toast(isAuto ? "AIM завершён" : "Остановлено");
    },
    
    registerHit() {
      if (!AppState.aim.running) return;
      AppState.aim.shots += 1;
      AppState.aim.hits += 1;
      Utils.haptic("impact", "light");
      this.moveTarget();
      this.updateUI();
    },
    
    registerMiss() {
      if (!AppState.aim.running) return;
      AppState.aim.shots += 1;
      Utils.haptic("impact", "light");
      this.updateUI();
    },
    
    sendResult() {
      const duration = AppState.aim.running ? (Utils.now() - AppState.aim.startedAt) : AppState.aim.durationMs;
      const accuracy = AppState.aim.shots > 0 ? (AppState.aim.hits / AppState.aim.shots) : 0;
      const score = Math.round(AppState.aim.hits * 100 + accuracy * 100);
      
      BotIntegration.sendData({
        action: "game_result",
        game: "aim",
        mode: "arcade",
        shots: AppState.aim.shots,
        hits: AppState.aim.hits,
        accuracy: accuracy,
        score: score,
        duration_ms: duration,
        profile: true
      });
    },
    
    setupEventListeners() {
      const { arena, target } = this.getElements();
      if (arena && target) {
        TouchHandler.onTap(target, () => this.registerHit(), { lockMs: 60 });
        TouchHandler.onTap(arena, () => this.registerMiss(), { lockMs: 60 });
      }
    }
  };

  // =========================
  // ✅ ZOMBIES GAME МЕНЕДЖЕР
  // =========================
  const ZombiesGame = {
    // ==================== Инициализация ====================
    init() {
      this.setupEngineHooks();
      this.setupEventListeners();
    },
    
    setupEngineHooks() {
      if (AppState.flags.zhudHooked) return;
      
      const engine = this.getEngine();
      if (!engine) return;
      
      try {
        if (engine.on) {
          engine.on("hud", (hud) => this.onHudUpdate(hud));
          engine.on("result", (result) => this.onGameResult(result));
        }
        
        AppState.flags.zhudHooked = true;
        Utils.log("Engine hooks installed");
      } catch (error) {
        Utils.error("Failed to setup engine hooks", error);
      }
    },
    
    setupEventListeners() {
      window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && AppState.isGameActive) this.exit();
      }, { passive: true });
      
      window.addEventListener("resize", Utils.throttle(() => {
        if (AppState.isGameActive && AppState.zombies.canvas) this.resizeCanvas();
      }, 250));
    },
    
    // ==================== Движки ====================
    getEngine() {
      return window.BCO_ZOMBIES || window.BCO_ZOMBIES_CORE || null;
    },
    
    getInputBridge() {
      if (!window.BCO_ZOMBIES_INPUT) {
        window.BCO_ZOMBIES_INPUT = {
          move: { x: 0, y: 0 },
          aim: { x: 0, y: 0 },
          firing: false,
          updatedAt: 0
        };
      }
      return window.BCO_ZOMBIES_INPUT;
    },

    // ✅ HARD HIDE TG BUTTONS (iOS WebView sometimes re-shows them)
    startTelegramHardHide() {
      if (!AppState.tg || AppState.flags.tgHardHideActive) return;
      AppState.flags.tgHardHideActive = true;

      const tick = () => {
        if (!AppState.flags.tgHardHideActive) return;
        if (!AppState.isGameActive) return;

        try { AppState.tg.MainButton.hide(); } catch {}
        try { AppState.tg.BackButton.hide(); } catch {}

        // Some clients obey these toggles better when called repeatedly
        try { AppState.tg.setHeaderColor?.("#07070b"); } catch {}
        try { AppState.tg.setBackgroundColor?.("#07070b"); } catch {}

        AppState.flags.tgHardHideTimer = setTimeout(tick, 220);
      };

      tick();
    },

    stopTelegramHardHide() {
      AppState.flags.tgHardHideActive = false;
      if (AppState.flags.tgHardHideTimer) {
        try { clearTimeout(AppState.flags.tgHardHideTimer); } catch {}
      }
      AppState.flags.tgHardHideTimer = null;
    },

    // ✅ CONTRACT: bump zoom by +0.5 (best-effort)
    bumpZoomOnce(delta = CONFIG.ZOOM_BUMP) {
      if (AppState.flags.zoomBumpedThisEnter) return false;
      AppState.flags.zoomBumpedThisEnter = true;

      const engine = this.getEngine();
      const core = window.BCO_ZOMBIES_CORE;

      const tryGetZoom = () => {
        const candidates = [
          () => engine?.getZoom?.(),
          () => engine?.zoom?.(),
          () => engine?.state?.zoom,
          () => core?.getZoom?.(),
          () => core?.zoom,
          () => core?.state?.zoom
        ];
        for (const fn of candidates) {
          try {
            const v = fn();
            if (Number.isFinite(+v)) return +v;
          } catch {}
        }
        return null;
      };

      const current = tryGetZoom();
      const next = Number.isFinite(current) ? (current + delta) : null;

      const trySetZoom = (val) => {
        let ok = false;
        const attempts = [
          () => engine?.setZoom?.(val),
          () => engine?.setScale?.(val),
          () => engine?.zoom?.(val),
          () => { if (engine?.state) engine.state.zoom = val; },
          () => core?.setZoom?.(val),
          () => core?.setScale?.(val),
          () => { if (core?.state) core.state.zoom = val; }
        ];
        for (const fn of attempts) {
          try {
            fn();
            ok = true;
          } catch {}
        }
        return ok;
      };

      if (next !== null) {
        const ok = trySetZoom(next);
        if (ok) Utils.log("Zoom bumped", { from: current, to: next });
        return ok;
      }

      // If we can't read current zoom, still try applying delta as absolute fallback (rare)
      const okFallback = trySetZoom(delta);
      if (okFallback) Utils.log("Zoom set fallback", { to: delta });
      return okFallback;
    },

    // ✅ CONTRACT: apply player scale + speed tuning (best-effort)
    applyGameplayTuningOnce() {
      if (AppState.flags.tuningAppliedThisEnter) return false;
      AppState.flags.tuningAppliedThisEnter = true;

      const scale = CONFIG.PLAYER_SCALE;
      const spd = CONFIG.PLAYER_SPEED_MULT;

      const engine = this.getEngine();
      const core = window.BCO_ZOMBIES_CORE;

      let ok = false;

      const attempts = [
        // player scale
        () => engine?.setPlayerScale?.(scale),
        () => engine?.playerScale?.(scale),
        () => engine?.tune?.({ playerScale: scale }),
        () => core?.setPlayerScale?.(scale),
        () => { if (core?.state) core.state.playerScale = scale; },

        // speed multiplier
        () => engine?.setPlayerSpeedMult?.(spd),
        () => engine?.setSpeedMult?.("player", spd),
        () => engine?.tune?.({ playerSpeedMult: spd }),
        () => core?.setPlayerSpeedMult?.(spd),
        () => { if (core?.state) core.state.playerSpeedMult = spd; },

        // combined (some engines accept a single tune call)
        () => engine?.tune?.({ playerScale: scale, playerSpeedMult: spd }),
        () => core?.tune?.({ playerScale: scale, playerSpeedMult: spd })
      ];

      for (const fn of attempts) {
        try { fn(); ok = true; } catch {}
      }

      if (ok) Utils.log("Gameplay tuning applied", { playerScale: scale, playerSpeedMult: spd });
      return ok;
    },
    
    // ==================== Управление игрой ====================
    setMode(mode) {
      AppState.state.zombies_mode = mode === "roguelike" ? "roguelike" : "arcade";
      
      const engine = this.getEngine();
      if (engine) {
        try { engine.setMode?.(mode); } catch {}
        try { engine.mode?.(mode); } catch {}
      }
      Storage.saveState();
    },
    
    async enter() {
      if (!AppState.zombies.overlay) this.buildOverlay();
      
      AppState.isGameActive = true;
      AppState.zombies.active = true;
      AppState.zombies.overlay.style.display = "block";

      // reset per-enter flags
      AppState.flags.zoomBumpedThisEnter = false;
      AppState.flags.tuningAppliedThisEnter = false;
      
      // 🔥 Жёстко прячем TG кнопки + запускаем hard-hide loop
      UIManager.updateTelegramButtons();
      this.startTelegramHardHide();
      
      // Скрываем интерфейс приложения
      this.hideAppChrome(true);
      
      if (AppState.tg) {
        try {
          AppState.tg.expand();
          AppState.tg.setHeaderColor?.("#07070b");
          AppState.tg.setBackgroundColor?.("#07070b");
        } catch {}
      }
      
      // Полноэкранный режим (best effort)
      await this.enterFullscreen();
      
      // ✅ Важно: правильно выставляем canvas/DPR ДО attach/start
      this.resizeCanvas();
      
      // Экономика
      this.resetEconomy();
      
      // Подключаем движок
      this.attachEngine();

      // ✅ apply gameplay tuning + zoom bump (best-effort, safe)
      this.applyGameplayTuningOnce();
      this.bumpZoomOnce(CONFIG.ZOOM_BUMP);
      
      // Запускаем игру
      this.startGame();
      
      // Pump ввода
      this.startInputPump();
      
      // anti-zoom
      TouchHandler.init();
      
      Utils.haptic("notification", "success");
      Utils.toast("Zombies: Fullscreen ▶");
      Utils.log("Zombies game started");
    },
    
    exit() {
      if (!AppState.isGameActive) return;
      
      AppState.isGameActive = false;
      AppState.zombies.active = false;
      
      this.stopGame("exit");
      this.stopInputPump();
      this.stopTelegramHardHide();
      
      if (AppState.zombies.overlay) {
        AppState.zombies.overlay.style.display = "none";
        this.closeModal();
      }
      
      this.hideAppChrome(false);
      this.exitFullscreen();
      
      UIManager.selectTab("home");
      UIManager.updateTelegramButtons();
      
      Utils.haptic("notification", "warning");
      Utils.toast("Zombies: Exit");
      Utils.log("Zombies game exited");
    },
    
    // ==================== Оверлей и UI ====================
    buildOverlay() {
      if (AppState.zombies.overlay) return AppState.zombies.overlay;
      
      const mount = Utils.qs("#zOverlayMount") || document.body;
      const overlay = Utils.createElement("div", "bco-z-overlay");
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-label", "Zombies Fullscreen");
      
      const canvas = Utils.createElement("canvas", "bco-z-canvas");
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      
      const topbar = this.buildTopBar();
      const hud = this.buildHUD();
      const controls = this.buildControls();
      const shop = this.buildShop();
      const modal = this.buildModal();
      
      overlay.appendChild(canvas);
      overlay.appendChild(topbar);
      overlay.appendChild(hud);
      overlay.appendChild(shop);
      overlay.appendChild(controls);
      overlay.appendChild(modal);
      
      mount.appendChild(overlay);
      
      AppState.zombies.overlay = overlay;
      AppState.zombies.canvas = canvas;
      AppState.zombies.hudPill = overlay.querySelector("#bcoHud1");
      AppState.zombies.hudPill2 = overlay.querySelector("#bcoHud2");
      AppState.zombies.shop = shop;
      AppState.zombies.modal = modal;
      AppState.zombies.modalTitle = modal.querySelector("#bcoZModalTitle");
      AppState.zombies.modalBody = modal.querySelector("#bcoZModalBody");
      
      this.setupJoysticks();
      this.setupOverlayHandlers();
      
      return overlay;
    },
    
    buildTopBar() {
      const topbar = Utils.createElement("div", "bco-z-topbar");
      
      const left = Utils.createElement("div", "left");
      left.innerHTML = `
        <div class="bco-z-title">🧟 Zombies Survival</div>
        <div class="bco-z-sub" id="bcoZSub">${AppState.state.zombies_mode.toUpperCase()} • ${AppState.state.zombies_map}</div>
      `;
      
      const right = Utils.createElement("div", "right");
      const buttons = [
        { text: "🛒 Shop", action: () => this.openShopModal() },
        { text: "🎭 Character", action: () => this.openCharacterModal() },
        { text: "📤 Send", action: () => this.sendResult("manual") },
        { text: "✖ Exit", action: () => this.exit(), className: "danger" }
      ];
      
      buttons.forEach(btn => {
        const button = Utils.createElement("button", `bco-z-mini ${btn.className || ""}`);
        button.type = "button";
        button.textContent = btn.text;
        TouchHandler.onTap(button, btn.action);
        right.appendChild(button);
      });
      
      topbar.appendChild(left);
      topbar.appendChild(right);
      return topbar;
    },
    
    buildHUD() {
      const hud = Utils.createElement("div", "bco-z-hud");
      
      const pill1 = Utils.createElement("div", "bco-z-pill", "❤️ — • 🔫 — • 💰 —");
      pill1.id = "bcoHud1";
      
      const pill2 = Utils.createElement("div", "bco-z-pill", "Wave — • Kills — • Quest —");
      pill2.id = "bcoHud2";
      
      hud.appendChild(pill1);
      hud.appendChild(pill2);
      return hud;
    },
    
    buildControls() {
      const controls = Utils.createElement("div", "bco-z-controls");
      
      const joyL = Utils.createElement("div", "bco-joy");
      joyL.innerHTML = `<div class="bco-joy-knob"></div>`;
      joyL.id = "joyLeft";
      
      const joyR = Utils.createElement("div", "bco-joy");
      joyR.innerHTML = `<div class="bco-joy-knob"></div>`;
      joyR.id = "joyRight";
      
      const fireBtn = Utils.createElement("div", "bco-fire", "FIRE");
      fireBtn.id = "fireButton";
      
      const leftContainer = Utils.createElement("div");
      leftContainer.style.cssText = "display: flex; gap: 12px;";
      leftContainer.appendChild(joyL);
      
      const rightContainer = Utils.createElement("div");
      rightContainer.style.cssText = "display: flex; gap: 12px;";
      rightContainer.appendChild(fireBtn);
      rightContainer.appendChild(joyR);
      
      controls.appendChild(leftContainer);
      controls.appendChild(rightContainer);
      return controls;
    },
    
    buildShop() {
      const shop = Utils.createElement("div", "bco-z-shop");
      shop.innerHTML = `
        <button class="bco-shopbtn primary" type="button" data-act="upgrade">⬆️ Upgrade</button>
        <button class="bco-shopbtn" type="button" data-act="reroll">🎲 Reroll</button>
        <button class="bco-shopbtn" type="button" data-act="reload">🔄 Reload</button>
        <button class="bco-shopbtn" type="button" data-perk="Jug">🧪 Jug</button>
        <button class="bco-shopbtn" type="button" data-perk="Speed">⚡ Speed</button>
        <button class="bco-shopbtn" type="button" data-perk="Mag">📦 Mag</button>
        <button class="bco-shopbtn" type="button" data-perk="Armor">🛡 Armor</button>
      `;
      return shop;
    },
    
    buildModal() {
      const modal = Utils.createElement("div", "bco-z-modal");
      modal.id = "bcoZModal";
      modal.innerHTML = `
        <div class="bco-z-card">
          <h3 id="bcoZModalTitle">Title</h3>
          <p id="bcoZModalDesc">Desc</p>
          <div id="bcoZModalBody"></div>
          <div style="display:flex; gap:10px; margin-top:12px; justify-content:flex-end;">
            <button class="bco-shopbtn" type="button" id="bcoZModalClose">Close</button>
          </div>
        </div>
      `;
      
      const card = modal.querySelector(".bco-z-card");
      if (card) {
        card.style.maxHeight = "82vh";
        card.style.overflow = "auto";
        card.style.webkitOverflowScrolling = "touch";
      }
      return modal;
    },
    
    setupJoysticks() {
      const joyLeft = Utils.qs("#joyLeft");
      const joyRight = Utils.qs("#joyRight");
      const knobLeft = joyLeft?.querySelector(".bco-joy-knob");
      const knobRight = joyRight?.querySelector(".bco-joy-knob");
      
      // ✅ FIX: Joystick находится внутри ZombiesGame
      if (joyLeft && knobLeft) AppState.zombies.joys.left = new ZombiesGame.Joystick(joyLeft, knobLeft, "left");
      if (joyRight && knobRight) AppState.zombies.joys.right = new ZombiesGame.Joystick(joyRight, knobRight, "right");
      
      // ✅ FIX: FIRE = hold-to-shoot (pointerdown/up), без onTap
      const fireBtn = Utils.qs("#fireButton");
      if (fireBtn) this.installFireHoldHandlers(fireBtn);
    },

    installFireHoldHandlers(fireBtn) {
      const input = this.getInputBridge();

      // Чтоб iOS не зумил/не скроллил на кнопке
      fireBtn.style.touchAction = "none";

      const setFiring = (on) => {
        AppState.zombies.input.firing = !!on;
        input.firing = !!on;
        input.updatedAt = Utils.now();
      };

      const onDown = (e, pointerId) => {
        // Не кликаем правой кнопкой мыши
        if (e && typeof e.button === "number" && e.button !== 0) return;

        try { e.preventDefault?.(); } catch {}
        try { e.stopPropagation?.(); } catch {}

        AppState.zombies.fire.active = true;
        AppState.zombies.fire.pointerId = pointerId;

        setFiring(true);
        Utils.haptic("impact", "light");
      };

      const onUp = (e, pointerId) => {
        if (!AppState.zombies.fire.active) return;
        if (AppState.zombies.fire.pointerId !== null && pointerId !== AppState.zombies.fire.pointerId) return;

        try { e.preventDefault?.(); } catch {}
        try { e.stopPropagation?.(); } catch {}

        AppState.zombies.fire.active = false;
        AppState.zombies.fire.pointerId = null;

        setFiring(false);
      };

      if (window.PointerEvent) {
        fireBtn.addEventListener("pointerdown", (e) => {
          try { fireBtn.setPointerCapture?.(e.pointerId); } catch {}
          onDown(e, e.pointerId);
        }, { passive: false });

        fireBtn.addEventListener("pointerup", (e) => onUp(e, e.pointerId), { passive: false });
        fireBtn.addEventListener("pointercancel", (e) => onUp(e, e.pointerId), { passive: false });
        fireBtn.addEventListener("pointerleave", (e) => onUp(e, e.pointerId), { passive: false });

        // Если палец отпустили где-то на экране — тоже выключаем
        window.addEventListener("pointerup", (e) => onUp(e, e.pointerId), { passive: true });
        window.addEventListener("pointercancel", (e) => onUp(e, e.pointerId), { passive: true });
      } else {
        fireBtn.addEventListener("touchstart", (e) => {
          const t = e.changedTouches?.[0];
          if (!t) return;
          onDown(e, t.identifier);
        }, { passive: false });

        fireBtn.addEventListener("touchend", (e) => {
          const t = e.changedTouches?.[0];
          if (!t) return;
          onUp(e, t.identifier);
        }, { passive: false });

        fireBtn.addEventListener("touchcancel", (e) => {
          const t = e.changedTouches?.[0];
          if (!t) return;
          onUp(e, t.identifier);
        }, { passive: false });

        window.addEventListener("touchend", (e) => {
          const t = e.changedTouches?.[0];
          if (!t) return;
          onUp(e, t.identifier);
        }, { passive: true });

        window.addEventListener("touchcancel", (e) => {
          const t = e.changedTouches?.[0];
          if (!t) return;
          onUp(e, t.identifier);
        }, { passive: true });
      }
    },
    
    setupOverlayHandlers() {
      const { overlay, shop, modal } = AppState.zombies;
      if (!overlay) return;
      
      TouchHandler.onTap(shop, (e) => {
        const button = e.target.closest(".bco-shopbtn");
        if (!button) return;
        
        const action = button.getAttribute("data-act");
        const perk = button.getAttribute("data-perk");
        
        Utils.haptic("impact", "light");
        if (action) this.shopAction(action);
        else if (perk) this.buyPerk(perk);
      }, { lockMs: 140 });
      
      const closeBtn = modal.querySelector("#bcoZModalClose");
      if (closeBtn) {
        TouchHandler.onTap(closeBtn, () => {
          Utils.haptic("impact", "light");
          this.closeModal();
        });
      }
      
      TouchHandler.onTap(modal, (e) => {
        if (e.target === modal) this.closeModal();
      }, { lockMs: 120 });
      
      overlay.addEventListener("touchmove", (e) => {
        if (!AppState.isGameActive) return;
        if (e.target.closest(".bco-z-card")) return;
        try { e.preventDefault(); } catch {}
      }, { passive: false });
    },
    
    // ==================== Джойстик класс ====================
    Joystick: class {
      constructor(root, knob, type) {
        this.root = root;
        this.knob = knob;
        this.type = type; // 'left' или 'right'
        
        this.active = false;
        this.pointerId = null;
        
        this.centerX = 0;
        this.centerY = 0;
        this.radius = 1;
        
        this.valueX = 0;
        this.valueY = 0;
        
        this.setupEventListeners();
        this.updatePosition();
        
        window.addEventListener("resize", () => {
          setTimeout(() => this.updatePosition(), 100);
        });
      }
      
      updatePosition() {
        const rect = this.root.getBoundingClientRect();
        this.centerX = rect.left + rect.width / 2;
        this.centerY = rect.top + rect.height / 2;
        this.radius = Math.max(1, Math.min(rect.width, rect.height) / 2 - 10);
      }
      
      setValues(x, y) {
        const length = Utils.length(x, y);
        const normalizedX = length > 0 ? x / length : 0;
        const normalizedY = length > 0 ? y / length : 0;
        const limitedLength = Math.min(1, length / this.radius);
        
        this.valueX = normalizedX * limitedLength;
        this.valueY = normalizedY * limitedLength;
        
        const knobX = this.valueX * (this.radius * 0.62);
        const knobY = this.valueY * (this.radius * 0.62);
        this.knob.style.transform = `translate(${knobX}px, ${knobY}px)`;
        
        this.updateInput();
      }
      
      updateInput() {
        const input = ZombiesGame.getInputBridge();
        
        if (this.type === 'left') {
          input.move.x = this.valueX;
          input.move.y = this.valueY;
        } else {
          input.aim.x = this.valueX;
          input.aim.y = this.valueY;
        }
        input.updatedAt = Utils.now();
      }
      
      setupEventListeners() {
        this.root.style.touchAction = "none";
        
        if (window.PointerEvent) {
          this.root.addEventListener("pointerdown", this.onPointerDown.bind(this), { passive: false });
          window.addEventListener("pointermove", this.onPointerMove.bind(this), { passive: true });
          window.addEventListener("pointerup", this.onPointerUp.bind(this), { passive: true });
          window.addEventListener("pointercancel", this.onPointerUp.bind(this), { passive: true });
        } else {
          this.root.addEventListener("touchstart", this.onTouchStart.bind(this), { passive: false });
          window.addEventListener("touchmove", this.onTouchMove.bind(this), { passive: true });
          window.addEventListener("touchend", this.onTouchEnd.bind(this), { passive: true });
          window.addEventListener("touchcancel", this.onTouchEnd.bind(this), { passive: true });
        }
      }
      
      onPointerDown(e) {
        if (this.active) return;
        try { e.preventDefault(); } catch {}
        
        this.active = true;
        this.pointerId = e.pointerId;
        
        try { this.root.setPointerCapture(e.pointerId); } catch {}
        
        this.updatePosition();
        this.onMove(e.clientX, e.clientY);
      }
      
      onPointerMove(e) {
        if (!this.active || e.pointerId !== this.pointerId) return;
        this.onMove(e.clientX, e.clientY);
      }
      
      onPointerUp(e) {
        if (!this.active || e.pointerId !== this.pointerId) return;
        this.reset();
      }
      
      onTouchStart(e) {
        if (this.active) return;
        try { e.preventDefault(); } catch {}
        
        const touch = e.changedTouches[0];
        if (!touch) return;
        
        this.active = true;
        this.pointerId = touch.identifier;
        this.updatePosition();
        this.onMove(touch.clientX, touch.clientY);
      }
      
      onTouchMove(e) {
        if (!this.active) return;
        const touch = Array.from(e.changedTouches).find(t => t.identifier === this.pointerId);
        if (!touch) return;
        this.onMove(touch.clientX, touch.clientY);
      }
      
      onTouchEnd(e) {
        if (!this.active) return;
        const touch = Array.from(e.changedTouches).find(t => t.identifier === this.pointerId);
        if (!touch) return;
        this.reset();
      }
      
      onMove(clientX, clientY) {
        const x = clientX - this.centerX;
        const y = clientY - this.centerY;
        this.setValues(x, y);
      }
      
      reset() {
        this.active = false;
        this.pointerId = null;
        this.setValues(0, 0);
      }
    },
    
    // ==================== Ввод и управление ====================
    startInputPump() {
      if (AppState.flags.inputPumpActive) return;
      
      const pump = () => {
        if (!AppState.isGameActive) return;
        
        const input = this.getInputBridge();
        const engine = this.getEngine();
        
        input.updatedAt = Utils.now();
        
        // Берём флаг firing из AppState (чтоб FIRE работал даже без bridge)
        input.firing = !!AppState.zombies.input.firing;
        
        if (engine) {
          try { engine.setMove?.(input.move.x, input.move.y); } catch {}
          try { engine.setAim?.(input.aim.x, input.aim.y); } catch {}
          try { engine.setFire?.(input.firing); } catch {}
          try { engine.input?.(input); } catch {}
        }
        
        const core = window.BCO_ZOMBIES_CORE;
        if (core) {
          try { core.setMove?.(input.move.x, input.move.y); } catch {}
          try { core.setAim?.(input.aim.x, input.aim.y); } catch {}
          try { core.setShooting?.(input.firing); } catch {}
        }
        
        requestAnimationFrame(pump);
      };
      
      requestAnimationFrame(pump);
      AppState.flags.inputPumpActive = true;
    },
    
    stopInputPump() {
      AppState.flags.inputPumpActive = false;
      // На выходе — гарантированно выключаем стрельбу
      AppState.zombies.input.firing = false;
      const input = this.getInputBridge();
      input.firing = false;
      input.aim.x = 0; input.aim.y = 0;
      input.move.x = 0; input.move.y = 0;
    },
    
    // ==================== Экономика ====================
    resetEconomy() {
      AppState.zombies.econ.coins = Utils.clampInt(AppState.state.z_coins || 0, 0, 999999);
      AppState.zombies.econ.lastKills = 0;
      AppState.zombies.econ.lastWave = 0;
      
      const engine = this.getEngine();
      if (engine) {
        try { engine.setCoins?.(AppState.zombies.econ.coins); } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core?.state) {
        try { core.state.coins = AppState.zombies.econ.coins; } catch {}
      }
    },
    
    addCoins(amount, reason = "") {
      const add = Utils.clampInt(amount, 0, 999999);
      if (add <= 0) return;
      
      AppState.zombies.econ.coins = Utils.clampInt((AppState.zombies.econ.coins || 0) + add, 0, 999999);
      AppState.state.z_coins = AppState.zombies.econ.coins;
      
      const engine = this.getEngine();
      if (engine) {
        try { engine.addCoins?.(add); } catch {}
        try { engine.setCoins?.(AppState.zombies.econ.coins); } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core?.state) {
        try { core.state.coins = AppState.zombies.econ.coins; } catch {}
      }
      
      Storage.saveState();
      if (reason) Utils.toast(`+${add} 💰 ${reason}`);
    },
    
    spendCoins(cost) {
      const amount = Utils.clampInt(cost, 0, 999999);
      if (AppState.zombies.econ.coins < amount) return false;
      
      AppState.zombies.econ.coins -= amount;
      AppState.state.z_coins = AppState.zombies.econ.coins;
      
      const engine = this.getEngine();
      if (engine) {
        try { engine.setCoins?.(AppState.zombies.econ.coins); } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core?.state) {
        try { core.state.coins = AppState.zombies.econ.coins; } catch {}
      }
      
      Storage.saveState();
      return true;
    },
    
    tryDropRelic() {
      if (AppState.state.z_wonder_unlocked) return;
      if (AppState.state.z_relics >= 5) return;
      if (AppState.state.zombies_mode !== "roguelike") return;
      
      const chance = Math.random();
      if (chance <= CONFIG.RELIC_DROP_CHANCE) {
        AppState.state.z_relics = Utils.clampInt((AppState.state.z_relics || 0) + 1, 0, 5);
        Storage.saveState();
        Utils.toast(`Реликвия найдена 🗿 (${AppState.state.z_relics}/5)`);
        
        if (AppState.state.z_relics >= 5) {
          AppState.state.z_wonder_unlocked = true;
          Storage.saveState();
          
          Utils.haptic("notification", "success");
          Utils.toast("ЧУДО-ОРУЖИЕ ОТКРЫТО 👑⚡");
          this.unlockWonderWeapon();
        }
      }
    },
    
    // ==================== Магазин и перки ====================
    shopAction(action) {
      const price = CONFIG.PRICES[action] || 0;
      
      if (AppState.state.zombies_mode === "roguelike") {
        if (!this.canAfford(price)) return;
        if (!this.spendCoins(price)) return;
      }
      
      let success = false;
      switch (action) {
        case "upgrade": success = this.upgradeWeapon(); break;
        case "reroll": success = this.rerollWeapon(); break;
        case "reload": success = this.reloadWeapon(); break;
      }
      
      if (success) {
        if (AppState.state.zombies_mode === "roguelike" && price > 0) Utils.toast(`-${price} 💰 ${action}`);
        this.updateHUD();
      } else {
        Utils.haptic("notification", "error");
        Utils.toast("Действие недоступно");
      }
    },
    
    buyPerk(perk) {
      const price = CONFIG.PRICES[perk] || 0;
      
      if (AppState.state.zombies_mode === "roguelike") {
        if (!this.canAfford(price)) return;
        if (!this.spendCoins(price)) return;
      }
      
      const success = this.purchasePerk(perk);
      if (success) {
        if (AppState.state.zombies_mode === "roguelike" && price > 0) Utils.toast(`-${price} 💰 ${perk}`);
        this.updateHUD();
      } else {
        Utils.haptic("notification", "error");
        Utils.toast(`Perk недоступен: ${perk}`);
      }
    },
    
    canAfford(price) {
      if (AppState.state.zombies_mode !== "roguelike") return true;
      if (AppState.zombies.econ.coins >= price) return true;
      Utils.haptic("notification", "error");
      Utils.toast(`Не хватает монет 💰 (${AppState.zombies.econ.coins}/${price})`);
      return false;
    },
    
    purchasePerk(perk) {
      const engine = this.getEngine();
      if (engine) {
        try { engine.buyPerk?.(perk); return true; } catch {}
        try { engine.buy?.(perk); return true; } catch {}
        try { engine.perk?.(perk); return true; } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core?.buyPerk) {
        try { return !!core.buyPerk(perk); } catch {}
      }
      return false;
    },
    
    upgradeWeapon() {
      const engine = this.getEngine();
      if (engine) {
        try { engine.upgrade?.(); return true; } catch {}
        try { engine.shop?.("upgrade"); return true; } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core?.buyUpgrade) {
        try { return !!core.buyUpgrade(); } catch {}
      }
      return false;
    },
    
    rerollWeapon() {
      const engine = this.getEngine();
      if (engine) {
        try { engine.reroll?.(); return true; } catch {}
        try { engine.roll?.(); return true; } catch {}
        try { engine.shop?.("reroll"); return true; } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core?.rerollWeapon) {
        try { return !!core.rerollWeapon(); } catch {}
      }
      return false;
    },
    
    reloadWeapon() {
      const engine = this.getEngine();
      if (engine) {
        try { engine.reload?.(); return true; } catch {}
        try { engine.shop?.("reload"); return true; } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core?.buyReload) {
        try { return !!core.buyReload(); } catch {}
      }
      
      if (core?.reload) {
        try { return !!core.reload(); } catch {}
      }
      return false;
    },
    
    unlockWonderWeapon() {
      const engine = this.getEngine();
      const weaponId = AppState.state.z_wonder_weapon || "CROWN_RAY";
      
      if (engine) {
        try { engine.unlockWeapon?.(weaponId); return true; } catch {}
        try { engine.unlock?.({ weapon: weaponId }); return true; } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core?.state) {
        try {
          core.state.relics = 5;
          core.state.wonderUnlocked = true;
          return true;
        } catch {}
      }
      return false;
    },
    
    // ==================== Модальные окна ====================
    closeModal() {
      if (AppState.zombies.modal) AppState.zombies.modal.classList.remove("show");
    },
    
    openShopModal() {
      this.buildOverlay();
      const { modal, modalTitle } = AppState.zombies;
      if (!modal) return;
      
      modal.classList.add("show");
      if (modalTitle) modalTitle.textContent = "🛒 Shop";
      
      const desc = modal.querySelector("#bcoZModalDesc");
      if (desc) {
        const coins = AppState.zombies.econ.coins;
        const relics = AppState.state.z_relics;
        const quest = AppState.state.z_wonder_unlocked
          ? `👑 Wonder weapon: UNLOCKED (${AppState.state.z_wonder_weapon})`
          : `🗿 Relics: ${relics}/5 (собери 5 → чудо-оружие)`;
        
        desc.textContent = AppState.state.zombies_mode === "roguelike"
          ? `Roguelike • 💰 ${coins} • ${quest}`
          : `Arcade • Быстрые действия и перки. (Экономика активна в Roguelike.)`;
      }
      
      const html = this.getShopModalHTML();
      this.setModalBody(html);
      this.setupShopModalHandlers();
    },
    
    openCharacterModal() {
      this.buildOverlay();
      const { modal, modalTitle } = AppState.zombies;
      if (!modal) return;
      
      modal.classList.add("show");
      if (modalTitle) modalTitle.textContent = "🎭 Character";
      
      const desc = modal.querySelector("#bcoZModalDesc");
      if (desc) desc.textContent = "Выбор персонажа/скина сохраняется (state + CloudStorage).";
      
      const html = this.getCharacterModalHTML();
      this.setModalBody(html);
      this.setupCharacterModalHandlers();
    },
    
    setModalBody(html) {
      const { modalBody } = AppState.zombies;
      if (!modalBody) return;
      
      const newBody = Utils.createElement("div");
      newBody.id = "bcoZModalBody";
      newBody.innerHTML = html;
      
      modalBody.replaceWith(newBody);
      AppState.zombies.modalBody = newBody;
      
      newBody.style.pointerEvents = "auto";
      newBody.style.touchAction = "pan-y";
    },
    
    getShopModalHTML() {
      const p = CONFIG.PRICES;
      const relics = AppState.state.z_relics;
      const wonderUnlocked = AppState.state.z_wonder_unlocked;
      const isRoguelike = AppState.state.zombies_mode === "roguelike";
      
      return `
        <div class="bco-z-grid">
          <div class="bco-z-choice">
            <div class="ttl">⬆️ Upgrade</div>
            <div class="sub">Апгрейд оружия/урона/скорости.</div>
            <button class="bco-shopbtn primary" type="button" data-act="upgrade">
              Buy ${isRoguelike ? `• ${p.upgrade}💰` : ""}
            </button>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">🎲 Reroll</div>
            <div class="sub">Переброс предложений.</div>
            <button class="bco-shopbtn" type="button" data-act="reroll">
              Roll ${isRoguelike ? `• ${p.reroll}💰` : ""}
            </button>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">🔄 Reload</div>
            <div class="sub">Патроны/перезарядка.</div>
            <button class="bco-shopbtn" type="button" data-act="reload">
              Reload ${isRoguelike ? `• ${p.reload}💰` : ""}
            </button>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">🧪 Jug</div>
            <div class="sub">Выживаемость.</div>
            <button class="bco-shopbtn" type="button" data-perk="Jug">
              Buy ${isRoguelike ? `• ${p.Jug}💰` : ""}
            </button>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">⚡ Speed</div>
            <div class="sub">Скорость/мувмент.</div>
            <button class="bco-shopbtn" type="button" data-perk="Speed">
              Buy ${isRoguelike ? `• ${p.Speed}💰` : ""}
            </button>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">📦 Mag</div>
            <div class="sub">Боезапас/магазин.</div>
            <button class="bco-shopbtn" type="button" data-perk="Mag">
              Buy ${isRoguelike ? `• ${p.Mag}💰` : ""}
            </button>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">🛡 Armor</div>
            <div class="sub">Снижение урона.</div>
            <button class="bco-shopbtn" type="button" data-perk="Armor">
              Buy ${isRoguelike ? `• ${p.Armor}💰` : ""}
            </button>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">🎮 Mode</div>
            <div class="sub">Arcade / Roguelike</div>
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
              <button class="bco-shopbtn" type="button" data-mode="arcade">Arcade</button>
              <button class="bco-shopbtn" type="button" data-mode="roguelike">Roguelike</button>
            </div>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">👑 Wonder Quest</div>
            <div class="sub">${wonderUnlocked ? "Открыто ✅" : `Реликвии: ${relics}/5`}</div>
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
              <button class="bco-shopbtn ${wonderUnlocked ? "primary" : ""}" type="button" data-wonder="status">
                ${wonderUnlocked ? "Equip/Grant" : "How to get"}
              </button>
              <button class="bco-shopbtn" type="button" data-wonder="reset">Reset quest</button>
            </div>
          </div>
        </div>
      `;
    },
    
    getCharacterModalHTML() {
      const isMale = AppState.state.character === "male";
      const isFemale = AppState.state.character === "female";
      
      return `
        <div class="bco-z-grid">
          <div class="bco-z-choice">
            <div class="ttl">👨 Male</div>
            <div class="sub">Текущий: ${isMale ? "✅" : "—"}</div>
            <button class="bco-shopbtn ${isMale ? "primary" : ""}" type="button" data-char="male">
              Select
            </button>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">👩 Female</div>
            <div class="sub">Текущий: ${isFemale ? "✅" : "—"}</div>
            <button class="bco-shopbtn ${isFemale ? "primary" : ""}" type="button" data-char="female">
              Select
            </button>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">🎨 Skin</div>
            <div class="sub">Сейчас: ${AppState.state.skin}</div>
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
              <button class="bco-shopbtn" type="button" data-skin="default">default</button>
              <button class="bco-shopbtn" type="button" data-skin="neon">neon</button>
              <button class="bco-shopbtn" type="button" data-skin="tactical">tactical</button>
              <button class="bco-shopbtn" type="button" data-skin="shadow">shadow</button>
            </div>
          </div>
          
          <div class="bco-z-choice">
            <div class="ttl">🖼 Render</div>
            <div class="sub">Под 3D переход (пока 2D ядро)</div>
            <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:10px;">
              <button class="bco-shopbtn" type="button" data-render="2d">2D</button>
              <button class="bco-shopbtn" type="button" data-render="3d">3D (beta)</button>
            </div>
          </div>
        </div>
      `;
    },
    
    setupShopModalHandlers() {
      const { modalBody } = AppState.zombies;
      if (!modalBody) return;
      
      TouchHandler.onTap(modalBody, async (e) => {
        const button = e.target.closest(".bco-shopbtn");
        if (!button) return;
        
        const action = button.getAttribute("data-act");
        const perk = button.getAttribute("data-perk");
        const mode = button.getAttribute("data-mode");
        const wonder = button.getAttribute("data-wonder");
        
        if (action) this.shopAction(action);
        if (perk) this.buyPerk(perk);
        
        if (mode) {
          this.setMode(mode);
          this.updateHUD();
          Utils.toast(`Mode: ${mode}`);
          await Storage.saveState();
          this.openShopModal();
        }
        
        if (wonder === "status") {
          if (AppState.state.z_wonder_unlocked) {
            const success = this.unlockWonderWeapon();
            Utils.toast(success ? `Equipped: ${AppState.state.z_wonder_weapon}` : "Wonder unlocked ✅");
          } else {
            Utils.toast("Реликвии падают в Roguelike с убийств. Собери 5.");
          }
        }
        
        if (wonder === "reset") {
          AppState.state.z_relics = 0;
          AppState.state.z_wonder_unlocked = false;
          await Storage.saveState();
          Utils.toast("Quest reset ✅");
          this.openShopModal();
        }
      }, { lockMs: 120 });
    },
    
    setupCharacterModalHandlers() {
      const { modalBody } = AppState.zombies;
      if (!modalBody) return;
      
      TouchHandler.onTap(modalBody, async (e) => {
        const button = e.target.closest(".bco-shopbtn");
        if (!button) return;
        
        const character = button.getAttribute("data-char");
        const skin = button.getAttribute("data-skin");
        const render = button.getAttribute("data-render");
        
        if (character) {
          AppState.state.character = character;
          await Storage.saveState();
          Utils.toast(`Character: ${character}`);
          
          const engine = this.getEngine();
          if (engine) {
            try { engine.setPlayerSkin?.(character, AppState.state.skin); } catch {}
            try { engine.open?.({ map: AppState.state.zombies_map, character, skin: AppState.state.skin }); } catch {}
          }
          this.openCharacterModal();
        }
        
        if (skin) {
          AppState.state.skin = skin;
          await Storage.saveState();
          Utils.toast(`Skin: ${skin}`);
          
          const engine = this.getEngine();
          if (engine) {
            try { engine.setPlayerSkin?.(AppState.state.character, skin); } catch {}
          }
          this.openCharacterModal();
        }
        
        if (render) {
          AppState.state.render = render === "3d" ? "3d" : "2d";
          await Storage.saveState();
          Utils.toast(`Render: ${AppState.state.render}`);
          
          const engine = this.getEngine();
          if (engine) {
            try { engine.setRenderMode?.(render); } catch {}
            try { engine.renderer?.(render); } catch {}
          }
          this.openCharacterModal();
        }
      }, { lockMs: 120 });
    },
    
    // ==================== HUD и обновления ====================
    updateHUD(hudData = null) {
      if (!AppState.zombies.overlay) return;
      const data = hudData || {};
      const state = AppState.state;
      
      const sub = AppState.zombies.overlay.querySelector("#bcoZSub");
      if (sub) sub.textContent = `${state.zombies_mode.toUpperCase()} • ${state.zombies_map}`;
      
      if (AppState.zombies.shop) {
        AppState.zombies.shop.style.opacity = state.zombies_mode === "roguelike" ? "1" : "0.85";
      }
      
      const health = data.hp ?? data.health ?? "—";
      const ammo = data.ammo ?? "—";
      const weapon = data.weapon ?? data.gun ?? "—";
      const wave = Utils.clampInt(data.wave ?? 0, 0, 999999) || "—";
      const kills = Utils.clampInt(data.kills ?? 0, 0, 999999) || "—";
      
      const coinsFromEngine = data.coins ?? data.money ?? null;
      const coins = coinsFromEngine !== null 
        ? coinsFromEngine 
        : (AppState.zombies.econ.coins ?? state.z_coins ?? 0);
      
      const quest = state.z_wonder_unlocked ? `👑 Wonder ✅` : `🗿 ${Utils.clampInt(state.z_relics ?? 0, 0, 5)}/5`;
      
      if (AppState.zombies.hudPill) {
        AppState.zombies.hudPill.textContent = `❤️ ${health} • 🔫 ${weapon} (${ammo}) • 💰 ${coins}`;
      }
      if (AppState.zombies.hudPill2) {
        AppState.zombies.hudPill2.textContent = `Wave ${wave} • Kills ${kills} • ${quest}`;
      }
    },
    
    onHudUpdate(hud) {
      if (!hud || typeof hud !== "object") return;
      this.updateEconomy(hud);
      this.updateHUD(hud);
    },
    
    updateEconomy(hud) {
      const kills = Utils.clampInt(hud.kills ?? hud.frags ?? 0, 0, 999999);
      const wave = Utils.clampInt(hud.wave ?? hud.round ?? 0, 0, 999999);
      
      if (kills > AppState.zombies.econ.lastKills) {
        const diff = kills - AppState.zombies.econ.lastKills;
        AppState.zombies.econ.lastKills = kills;
        
        if (AppState.state.zombies_mode === "roguelike") {
          this.addCoins(diff * CONFIG.COINS_PER_KILL);
          for (let i = 0; i < diff; i++) this.tryDropRelic();
        }
      }
      
      if (wave > AppState.zombies.econ.lastWave) {
        const diff = wave - AppState.zombies.econ.lastWave;
        AppState.zombies.econ.lastWave = wave;
        
        if (AppState.state.zombies_mode === "roguelike") {
          this.addCoins(diff * CONFIG.COINS_PER_WAVE, `Wave ${wave}`);
        }
      }
    },
    
    // ==================== Движок и Canvas ====================
    attachEngine() {
      const { canvas } = AppState.zombies;
      if (!canvas) return;
      
      const engine = this.getEngine();
      if (engine) {
        try { engine.setCanvas?.(canvas); } catch {}
        try { engine.canvas?.(canvas); } catch {}
        try { engine.attach?.(canvas); } catch {}
        
        try {
          engine.open?.({
            map: AppState.state.zombies_map,
            character: AppState.state.character,
            skin: AppState.state.skin,
            mode: AppState.state.zombies_mode
          });
        } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core) {
        try { core.resize?.(canvas.width, canvas.height); } catch {}
      }
    },
    
    resizeCanvas() {
      const { canvas } = AppState.zombies;
      if (!canvas) return;
      
      const dpr = window.devicePixelRatio || 1;
      const width = window.innerWidth;
      const height = window.innerHeight;
      
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      
      const engine = this.getEngine();
      if (engine) {
        try { engine.resize?.(width, height); } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core) {
        try { core.resize?.(width, height); } catch {}
      }
    },
    
    startGame() {
      const engine = this.getEngine();
      if (engine) {
        try {
          engine.start?.({
            map: AppState.state.zombies_map,
            mode: AppState.state.zombies_mode,
            character: AppState.state.character,
            skin: AppState.state.skin
          });
          return;
        } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core?.start) {
        try {
          core.start(
            AppState.state.zombies_mode,
            AppState.zombies.canvas?.width || 1,
            AppState.zombies.canvas?.height || 1,
            {
              map: AppState.state.zombies_map,
              character: AppState.state.character,
              skin: AppState.state.skin,
              weaponKey: "SMG"
            }
          );
        } catch {}
      }
    },
    
    stopGame(reason = "manual") {
      const engine = this.getEngine();
      if (engine) {
        try { engine.stop?.(reason); } catch {}
        try { engine.stop?.(); } catch {}
      }
      
      const core = window.BCO_ZOMBIES_CORE;
      if (core?.stop) {
        try { core.stop?.(); } catch {}
      }
    },
    
    // ==================== Результаты и отправка ====================
    onGameResult(result) {
      const data = result || {};
      const mode = AppState.state.zombies_mode;
      const modeKey = mode === "roguelike" ? "roguelike" : "arcade";
      
      const score = Utils.clampInt(data.score ?? data.points ?? 0, 0, 999999999);
      if (!AppState.state.z_best) AppState.state.z_best = { arcade: 0, roguelike: 0 };
      
      const currentBest = AppState.state.z_best[modeKey] || 0;
      AppState.state.z_best[modeKey] = Math.max(currentBest, score);
      
      AppState.state.z_coins = Utils.clampInt(AppState.zombies.econ.coins ?? AppState.state.z_coins ?? 0, 0, 999999);
      Storage.saveState();
      
      this.sendResult("game_end", data);
    },
    
    sendResult(reason = "manual", extra = {}) {
      const payload = {
        action: "game_result",
        game: "zombies",
        mode: AppState.state.zombies_mode,
        map: AppState.state.zombies_map,
        reason,
        profile: true,
        coins: AppState.state.z_coins,
        relics: AppState.state.z_relics,
        wonder_unlocked: AppState.state.z_wonder_unlocked,
        wonder_weapon: AppState.state.z_wonder_unlocked ? AppState.state.z_wonder_weapon : null,
        ...extra
      };
      BotIntegration.sendData(payload);
    },
    
    // ==================== Fullscreen и UI ====================
    hideAppChrome(hide) {
      const header = Utils.qs(".app-header");
      const topTabs = Utils.qs(".top-tabs");
      const bottomNav = Utils.qs(".bottom-nav");
      
      if (header) header.style.display = hide ? "none" : "";
      if (topTabs) topTabs.style.display = hide ? "none" : "";
      if (bottomNav) bottomNav.style.display = hide ? "none" : "";
      
      document.documentElement.classList.toggle("bco-game", hide);
      document.body.classList.toggle("bco-game", hide);
      document.body.style.overflow = hide ? "hidden" : "";
    },
    
    async enterFullscreen() {
      try {
        if (!AppState.zombies.overlay) return false;
        if (document.fullscreenElement) return true;
        
        if (AppState.zombies.overlay.requestFullscreen) {
          await AppState.zombies.overlay.requestFullscreen({ navigationUI: "hide" });
          return true;
        }
        return false;
      } catch (error) {
        Utils.error("Fullscreen failed", error);
        return false;
      }
    },
    
    exitFullscreen() {
      try {
        if (document.fullscreenElement) document.exitFullscreen?.();
      } catch {}
    }
  };

  // =========================
  // ✅ ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ
  // =========================
  const App = {
    async init() {
      try {
        window.__BCO_JS_OK__ = true;
        
        if (document.readyState !== "complete") {
          await new Promise(resolve => {
            if (document.readyState === "complete") resolve();
            else document.addEventListener("DOMContentLoaded", resolve, { once: true });
          });
        }
        
        await this.setup();
        this.start();
        Utils.log("Application initialized successfully");
      } catch (error) {
        Utils.error("Application initialization failed", error);
        this.showError("Ошибка инициализации приложения");
      }
    },
    
    async setup() {
      this.initTelegram();
      const stateSource = await Storage.loadState();
      
      const statSession = Utils.qs("#statSession");
      if (statSession) statSession.textContent = stateSource.toUpperCase();
      
      await Storage.loadChat();
      
      ThemeManager.init();
      TouchHandler.init();
      UIManager.init();
      ChatManager.init();
      AimGame.init();
      AimGame.setupEventListeners();
      ZombiesGame.init();
      
      this.updateBuildTag();
    },
    
    initTelegram() {
      if (!AppState.tg) {
        Utils.log("Running in browser mode (no Telegram)");
        return;
      }
      
      try {
        AppState.tg.ready();
        AppState.tg.expand();
        this.setupDebugInfo();
        
        const statOnline = Utils.qs("#statOnline");
        if (statOnline) {
          const hasUser = !!AppState.tg.initDataUnsafe?.user?.id;
          statOnline.textContent = hasUser ? "TG_WEBVIEW" : "TG_NOUSER";
        }
        
        Utils.log("Telegram WebApp initialized");
      } catch (error) {
        Utils.error("Telegram initialization failed", error);
      }
    },
    
    setupDebugInfo() {
      if (!AppState.tg) return;
      
      const dbgUser = Utils.qs("#dbgUser");
      const dbgChat = Utils.qs("#dbgChat");
      const dbgInit = Utils.qs("#dbgInit");
      
      if (dbgUser) dbgUser.textContent = AppState.tg.initDataUnsafe?.user?.id ?? "—";
      if (dbgChat) dbgChat.textContent = AppState.tg.initDataUnsafe?.chat?.id ?? "—";
      if (dbgInit) {
        const hasInit = !!(AppState.tg.initData && String(AppState.tg.initData).length > 10);
        dbgInit.textContent = hasInit ? "ok" : "empty";
      }
    },
    
    updateBuildTag() {
      const buildText = AppState.buildId !== "__BUILD__" 
        ? `build ${AppState.buildId} • v${CONFIG.VERSION}`
        : `v${CONFIG.VERSION}`;
      
      const buildTag = Utils.qs("#buildTag");
      if (buildTag) buildTag.textContent = buildText;
    },
    
    start() {
      UIManager.selectTab("home");
      
      const hash = window.location.hash.replace("#", "").trim();
      if (hash && ["home", "coach", "vod", "settings", "game"].includes(hash)) {
        UIManager.selectTab(hash);
      }
      
      UIManager.updateTelegramButtons();
      AppState.isInitialized = true;
      Utils.toast("BCO Mini App загружен ✅");
    },
    
    showError(message) {
      alert(`BCO Error: ${message}\n\nPlease refresh the page.`);
      const errorDiv = Utils.createElement("div", "bco-error-overlay");
      errorDiv.innerHTML = `
        <div class="bco-error-card">
          <h3>⚠️ Ошибка загрузки</h3>
          <p>${Utils.escapeHtml(message)}</p>
          <button onclick="window.location.reload()">Перезагрузить</button>
        </div>
      `;
      document.body.appendChild(errorDiv);
    },
    
    getState() {
      return { config: CONFIG, appState: AppState, utils: Utils };
    },
    
    resetApp() {
      if (confirm("Сбросить все данные приложения?")) {
        localStorage.clear();
        window.location.reload();
      }
    }
  };

  // =========================
  // ✅ ЗАПУСК ПРИЛОЖЕНИЯ
  // =========================
  window.BCO_APP = App;
  window.BCO_UTILS = Utils;
  window.BCO_STORAGE = Storage;
  window.BCO_ZOMBIES_MANAGER = ZombiesGame;
  
  App.init().catch(error => {
    console.error("Fatal app error:", error);
  });

})();
