// latency_probe.js
// Auto mouth→ear latency logger.
// Exposes BOTH LatencyProbe.autoAttach (auto) and LatencyProbe.attachUI (manual).
// Designed to be resilient if another script previously defined LatencyProbe.

(function (global) {
    const defaults = {
      localThreshold: 0.02,
      remoteThreshold: 0.02,
      holdOnFrames: 3,     // frames above threshold for onset
      holdOffFrames: 6,    // frames below threshold for offset
      remoteTimeoutMs: 8000,
      cooldownMs: 300,
    };
  
    function rms(analyser, buf) {
      analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) { const v = buf[i]; sum += v * v; }
      return Math.sqrt(sum / buf.length);
    }
  
    function makeMeter(ctx, stream) {
      const src = ctx.createMediaStreamSource(stream);
      const an = ctx.createAnalyser();
      an.fftSize = 2048;
      src.connect(an);
      const buf = new Float32Array(an.fftSize);
      return () => rms(an, buf);
    }
  
    class AutoLatencyLogger {
      constructor({ localTrack, remoteStream, opts = {}, onSample, onSummary, logFn = console.log }) {
        this.opts = { ...defaults, ...opts };
        this.ctx = new (global.AudioContext || global.webkitAudioContext)();
        this.localTrack = localTrack;
        this.remoteStream = remoteStream;
        this.onSample = onSample;
        this.onSummary = onSummary;
        this.log = (...a) => logFn(...a);
  
        const localMs = new MediaStream([localTrack.mediaStreamTrack]);
        this.getLocal = makeMeter(this.ctx, localMs);
        this.getRemote = makeMeter(this.ctx, remoteStream);
  
        this.state = 'IDLE';
        this.overLocal = 0;
        this.overRemote = 0;
        this.underRemote = 0;
        this.tLocal = 0;
        this.results = [];
        this.ignoredRemoteOnly = 0;
  
        this.running = false;
        this._raf = null;
        this._tick = this._tick.bind(this);
      }
  
      async start() {
        if (this.running) return;
        if (this.ctx.state !== 'running') await this.ctx.resume();
        this.running = true;
        this._raf = requestAnimationFrame(this._tick);
        this.log('⏱️ Auto latency logger started');
      }
  
      stop() {
        this.running = false;
        if (this._raf) cancelAnimationFrame(this._raf);
        this._raf = null;
        this.log('⏹️ Auto latency logger stopped');
      }
  
      _tick() {
        if (!this.running) return;
  
        const now = performance.now();
        const lvlLocal = this.getLocal();
        const lvlRemote = this.getRemote();
  
        this.overLocal  = (lvlLocal  >= this.opts.localThreshold)  ? (this.overLocal  + 1) : 0;
        this.overRemote = (lvlRemote >= this.opts.remoteThreshold) ? (this.overRemote + 1) : 0;
        this.underRemote= (lvlRemote <  this.opts.remoteThreshold) ? (this.underRemote+ 1) : 0;
  
        switch (this.state) {
          case 'IDLE': {
            if (this.overRemote >= this.opts.holdOnFrames) {
              this.ignoredRemoteOnly++;
              this.state = 'IN_REMOTE';
              this.log(`(ignoring bot-only speech #${this.ignoredRemoteOnly})`);
              break;
            }
            if (this.overLocal >= this.opts.holdOnFrames) {
              this.tLocal = now;
              this.state = 'WAIT_REMOTE';
              this.deadline = now + this.opts.remoteTimeoutMs;
              this.log('🎙️ local onset');
            }
            break;
          }
          case 'WAIT_REMOTE': {
            if (now > this.deadline) {
              this.log('⌛ remote onset timeout; resetting');
              this.state = 'IDLE';
              break;
            }
            if (this.overRemote >= this.opts.holdOnFrames) {
              const tRemote = now;
              const ms = tRemote - this.tLocal;
              this.results.push(ms);
              this.log(`🔊 latency: ${Math.round(ms)} ms`);
              this.onSample && this.onSample(ms, [...this.results]);
              this.state = 'IN_REMOTE';
              this.underRemote = 0;
            }
            break;
          }
          case 'IN_REMOTE': {
            if (this.underRemote >= this.opts.holdOffFrames) {
              this.state = 'COOLDOWN';
              this.cooldownUntil = now + this.opts.cooldownMs;
              if (this.results.length) {
                const sum = this.results.reduce((a, b) => a + b, 0);
                const avg = sum / this.results.length;
                const min = Math.min(...this.results);
                const max = Math.max(...this.results);
                this.onSummary && this.onSummary({ count: this.results.length, avg, min, max });
              }
            }
            break;
          }
          case 'COOLDOWN': {
            if (now >= this.cooldownUntil) {
              this.state = 'IDLE';
              this.overLocal = this.overRemote = this.underRemote = 0;
            }
            break;
          }
        }
  
        this._raf = requestAnimationFrame(this._tick);
      }
    }
  
    // ---------- Manual UI helper (kept for compatibility) ----------
    async function measureSeries({ room, localTrack, remoteAudioEl, samples = 5, opts = {}, logEl }) {
      if (!localTrack || !remoteAudioEl || !remoteAudioEl.srcObject) {
        throw new Error("probe not ready (need localTrack and remoteAudioEl.srcObject)");
      }
      const ctx = new (global.AudioContext || global.webkitAudioContext)();
      const results = [];
      const getLocal = makeMeter(ctx, new MediaStream([localTrack.mediaStreamTrack]));
      const getRemote = makeMeter(ctx, remoteAudioEl.srcObject);
  
      if (ctx.state !== 'running') await ctx.resume();
  
      async function waitOnset(getLvl, thr, hold, timeoutMs, label) {
        const start = performance.now(); let over = 0;
        return await new Promise((resolve, reject) => {
          function tick() {
            const now = performance.now();
            if (now - start > timeoutMs) return reject(new Error(`${label} onset timeout`));
            over = getLvl() >= thr ? over + 1 : 0;
            if (over >= hold) return resolve(now);
            requestAnimationFrame(tick);
          }
          requestAnimationFrame(tick);
        });
      }
  
      for (let i = 0; i < samples; i++) {
        logEl && (logEl.textContent = `Sample ${i + 1}/${samples}: say “beep”...`);
        try {
          const t0 = await waitOnset(getLocal, 0.02, 3, 5000, 'local speech');
          logEl && (logEl.textContent = `Listening for echo…`);
          const t1 = await waitOnset(getRemote, 0.02, 3, 8000, 'remote playback');
          const ms = t1 - t0;
          results.push(ms);
          logEl && (logEl.textContent = `Sample ${i + 1}: ${Math.round(ms)} ms`);
          await new Promise(r => setTimeout(r, 800));
        } catch (e) {
          console.warn('Latency sample failed:', e);
          logEl && (logEl.textContent = `Sample ${i + 1} failed: ${e.message}`);
        }
      }
      const ok = results.length;
      const avg = ok ? results.reduce((a,b)=>a+b,0)/ok : NaN;
      const summary = ok ? `Avg over ${ok}: ${Math.round(avg)} ms` : `No successful samples`;
      logEl && (logEl.textContent = summary);
      return { results, avg };
    }
  
    function attachUI({ room, localTrack, remoteAudioEl, logSelector = "#latencyLog", onceBtn = "#latency1", multiBtn = "#latency5" }) {
      const logEl = document.querySelector(logSelector);
      const one = document.querySelector(onceBtn);
      const five = document.querySelector(multiBtn);
  
      const run1 = async () => {
        one.disabled = true; five.disabled = true;
        try { await measureSeries({ room, localTrack, remoteAudioEl, samples: 1, logEl }); }
        finally { one.disabled = false; five.disabled = false; }
      };
  
      const run5 = async () => {
        one.disabled = true; five.disabled = true;
        try { await measureSeries({ room, localTrack, remoteAudioEl, samples: 5, logEl }); }
        finally { one.disabled = false; five.disabled = false; }
      };
  
      one && (one.onclick = run1);
      five && (five.onclick = run5);
      return { run1, run5 };
    }
  
    function autoAttach({ room, localTrack, remoteAudioEl, logSelector = '#latencyLog' }) {
      const logEl = document.querySelector(logSelector);
      const print = (s) => { if (logEl) logEl.textContent = s; }
      const append = (s) => {
        if (!logEl) return;
        logEl.textContent = (logEl.textContent || '') + (logEl.textContent ? '\n' : '') + s;
        logEl.scrollTop = logEl.scrollHeight;
      };
  
      const logger = new AutoLatencyLogger({
        localTrack,
        remoteStream: remoteAudioEl.srcObject,
        onSample: (ms, all) => append(`sample ${all.length}: ${Math.round(ms)} ms`),
        onSummary: ({ count, avg, min, max }) =>
          print(`auto: ${count} samples — avg ${Math.round(avg)} ms (min ${Math.round(min)}, max ${Math.round(max)})`),
        logFn: (...a) => console.log('[latency]', ...a),
      });
      logger.start();
      return logger;
    }
  
    // --------- DEFENSIVE EXPORT (don’t clobber prior versions) ---------
    const ns = global.LatencyProbe = global.LatencyProbe || {};
    ns.autoAttach = autoAttach;
    ns.attachUI = ns.attachUI || attachUI; // keep manual API if someone still uses it
    // sanity log so you can verify the export
    // console.log('LatencyProbe export', Object.keys(ns));
  
  })(window);
  