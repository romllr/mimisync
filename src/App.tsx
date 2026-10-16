import { useCallback, useEffect, useRef, useState } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  AudioLines,
  Check,
  ChevronDown,
  Clapperboard,
  Cpu,
  Film,
  FolderOpen,
  Layers3,
  ListVideo,
  LoaderCircle,
  MonitorPlay,
  Play,
  Plus,
  ScanFace,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Terminal,
  Upload,
  X,
  Zap,
} from "lucide-react";
import {
  api,
  connection,
  desktop,
  exportResult,
  importMedia,
  type Hardware,
  type Job,
  type Media,
  type Model,
} from "./api";
const names: Record<string, string> = {
  "musetalk-1.5": "MuseTalk 1.5",
  "latentsync-1.5": "LatentSync 1.5",
  "latentsync-1.6": "LatentSync 1.6",
};
const duration = (n: number) =>
  `${Math.floor(n / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(n % 60)
    .toString()
    .padStart(2, "0")}`;
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
export default function App() {
  const [tab, setTab] = useState("studio"),
    [media, setMedia] = useState<Media[]>([]),
    [models, setModels] = useState<Model[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [hw, setHw] = useState<Hardware | null>(null),
    [online, setOnline] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [videoId, setVideoId] = useState(""),
    [audioId, setAudioId] = useState(""),
    [model, setModel] = useState("musetalk-1.5"),
    [automatic, setAutomatic] = useState(true),
    [preset, setPreset] = useState("balanced"),
    [start, setStart] = useState(0),
    [seconds, setSeconds] = useState(5),
    [advanced, setAdvanced] = useState(false),
    [steps, setSteps] = useState(30),
    [guidance, setGuidance] = useState(1.5),
    [batch, setBatch] = useState(4),
    [margin, setMargin] = useState(10),
    [cheek, setCheek] = useState(90),
    [parsing, setParsing] = useState("jaw"),
    [seed, setSeed] = useState(1247);
  const [selected, setSelected] = useState<string | null>(null),
    [logs, setLogs] = useState(""),
    [conn, setConn] = useState<{ url: string; token: string } | null>(null),
    [comparison, setComparison] = useState(false),
    [reviewed, setReviewed] = useState(false),
    [preflight, setPreflight] = useState<{
      id: string;
      issues: string[];
      license: string;
    } | null>(null);
  const initialRoute = useRef(false);
  useEffect(() => {
    if (online && !initialRoute.current) {
      initialRoute.current = true;
      if (!models.some((m) => m.ready)) setTab("models");
    }
  }, [online, models]);
  const originalRef = useRef<HTMLVideoElement>(null),
    resultRef = useRef<HTMLVideoElement>(null);
  const refresh = useCallback(async () => {
    try {
      const [h, m, j, f] = await Promise.all([
        api<Hardware>("/system"),
        api<Model[]>("/models"),
        api<Job[]>("/jobs"),
        api<Media[]>("/media"),
      ]);
      setHw(h);
      setModels(m);
      setJobs(j);
      setMedia(f);
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
    if (desktop)
      void connection()
        .then(setConn)
        .catch((e) => setError(message(e)));
    const timer = setInterval(() => void refresh(), 3000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (automatic && hw?.recommendation) setModel(hw.recommendation);
  }, [automatic, hw?.recommendation]);
  useEffect(() => {
    if (!selected) {
      setLogs("");
      return;
    }
    let active = true;
    const load = () =>
      api<{ text: string }>(`/jobs/${selected}/logs`)
        .then((x) => {
          if (active) setLogs(x.text);
        })
        .catch(() => {});
    void load();
    const timer = setInterval(load, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [selected]);
  const video = media.find((m) => m.id === videoId),
    audio = media.find((m) => m.id === audioId),
    engine = models.find((m) => m.id === model),
    current = jobs.find((j) => j.id === selected),
    active = jobs.filter((j) => ["running", "queued"].includes(j.status));
  const mediaUrl = (id: string) =>
    conn
      ? `${conn.url}/media/${id}/file?token=${encodeURIComponent(conn.token)}`
      : undefined;
  const resultUrl = (id: string) =>
    conn
      ? `${conn.url}/jobs/${id}/result?token=${encodeURIComponent(conn.token)}`
      : undefined;
  async function action(fn: () => Promise<unknown>) {
    setError("");
    setBusy(true);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function pick(kind: "video" | "audio") {
    await action(async () => {
      if (!desktop)
        throw new Error(
          "A importação está disponível no aplicativo Tauri. Execute npm run desktop.",
        );
      const path = await open({
        multiple: false,
        filters: [
          {
            name: kind === "video" ? "Vídeo" : "Áudio",
            extensions: kind === "video" ? ["mp4", "mov"] : ["mp3", "wav"],
          },
        ],
      });
      if (typeof path === "string") {
        const m = await importMedia(path);
        if (m.kind !== kind) throw new Error("Tipo de mídia inesperado");
        if (kind === "video") setVideoId(m.id);
        else setAudioId(m.id);
      }
    });
  }
  async function render(preview: boolean) {
    await action(async () => {
      const params = advanced
        ? {
            steps,
            guidance,
            batch_size: batch,
            extra_margin: margin,
            cheek_width: cheek,
            parsing_mode: parsing,
            seed,
          }
        : {};
      const job = await api<Job>("/jobs", {
        model,
        video_id: videoId,
        audio_id: audioId,
        preset,
        preview,
        start,
        preview_seconds: seconds,
        params,
      });
      setSelected(job.id);
    });
  }
  async function install(id: string, kind: string) {
    await action(async () => {
      const job = await api<Job>(`/models/${id}/actions`, {
        action: kind,
        licenses_reviewed: reviewed,
      });
      setSelected(job.id);
      setTab("queue");
    });
  }
  async function exportVideo(job: Job) {
    await action(async () => {
      const path = await save({
        defaultPath: `mimisync-${job.id.slice(0, 8)}.mp4`,
        filters: [{ name: "MP4 H.264", extensions: ["mp4"] }],
      });
      if (path) await exportResult(job.id, path);
    });
  }
  function sync() {
    const a = originalRef.current,
      b = resultRef.current;
    if (a && b && current) {
      const offset = current.start ?? 0;
      if (Math.abs(a.currentTime - (b.currentTime + offset)) > 0.12)
        a.currentTime = b.currentTime + offset;
      a.playbackRate = b.playbackRate;
      if (b.paused) a.pause();
      else void a.play().catch(() => {});
    }
  }
  const canRender = online && !!video && !!audio && !!engine?.ready && !busy;
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" onClick={() => setTab("studio")}>
          <span className="brand-icon">
            <AudioLines size={22} />
          </span>
          mimisync<span className="version">BETA</span>
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <nav>
          {[
            { id: "studio", icon: Clapperboard, label: "Estúdio" },
            { id: "models", icon: Layers3, label: "Modelos de IA" },
            { id: "queue", icon: ListVideo, label: "Fila de processamento" },
          ].map((n) => (
            <button
              key={n.id}
              className={tab === n.id ? "nav active" : "nav"}
              onClick={() => setTab(n.id)}
            >
              <n.icon size={18} />
              {n.label}
              {n.id === "queue" && active.length > 0 && <b>{active.length}</b>}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={19} />
          <strong>Seu conteúdo fica com você.</strong>
          <p>Inferência local. Sem envio de vídeos para APIs de IA.</p>
        </div>
        <div className="gpu-card">
          <div className="eyebrow">
            <span className={hw?.gpus.length ? "dot" : "dot muted"} /> HARDWARE
            LOCAL
          </div>
          <strong>{hw?.gpus[0]?.name ?? "GPU não detectada"}</strong>
          <div className="meter">
            <span
              style={{
                width: hw?.gpus[0]
                  ? `${100 * (1 - hw.gpus[0].free_mb / hw.gpus[0].total_mb)}%`
                  : "0%",
              }}
            />
          </div>
          <small>
            {hw?.gpus[0]
              ? `${((hw.gpus[0].total_mb - hw.gpus[0].free_mb) / 1024).toFixed(1)} / ${(hw.gpus[0].total_mb / 1024).toFixed(0)} GB VRAM`
              : "Requer NVIDIA + CUDA"}
          </small>
        </div>
        <button className="system-link" onClick={() => setTab("system")}>
          <Settings2 size={16} /> Diagnóstico do sistema{" "}
          <ArrowRight size={14} />
        </button>
        <div className="sidebar-bottom">
          <span className="avatar">M</span>
          <div>
            Mimisync Local<small>Windows 11 · WSL2</small>
          </div>
          <span className="local-badge">LOCAL</span>
        </div>
      </aside>
      <div className="main">
        <header>
          <div className="breadcrumbs">
            Workspace <span>/</span>{" "}
            <strong>
              {tab === "studio"
                ? "Estúdio"
                : tab === "models"
                  ? "Modelos de IA"
                  : tab === "queue"
                    ? "Processamento"
                    : "Sistema"}
            </strong>
          </div>
          <div className="header-right">
            <span className="private">
              <ShieldCheck size={14} /> Processamento privado
            </span>
            <span className="divider" />
            <span className={online ? "connection online" : "connection"}>
              <i />
              {online ? "Backend conectado" : "Backend desconectado"}
            </span>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">LOCAL AI LIP SYNC</div>
              <h1>
                {tab === "studio"
                  ? "Dê uma nova voz ao seu vídeo."
                  : tab === "models"
                    ? "Escolha o motor da sua criação."
                    : tab === "queue"
                      ? "Cada trabalho, em um só lugar."
                      : "Seu ambiente de produção."}
              </h1>
              <p>
                {tab === "studio"
                  ? "Sincronização labial com IA, do primeiro frame ao último. Tudo na sua máquina."
                  : tab === "models"
                    ? "Repositórios oficiais. Ambientes isolados. Checkpoints sob seu controle."
                    : tab === "queue"
                      ? "Acompanhe etapas, resultados e logs reais de processamento."
                      : "Compatibilidade e recursos detectados na máquina de inferência."}
              </p>
            </div>
            <span className="outline-pill">
              <span className="dot" /> 100% local
            </span>
          </div>
          {error && (
            <div className="alert" role="alert">
              <span>{error}</span>
              <button onClick={() => setError("")} aria-label="Fechar erro">
                <X size={16} />
              </button>
            </div>
          )}
          {!online && (
            <div className="notice">
              <Cpu size={17} />
              <span>
                {desktop
                  ? "Aguardando o backend Python. Consulte o terminal se a conexão não iniciar."
                  : "Modo de interface: abra pelo Tauri para importar arquivos e executar inferência local."}
              </span>
            </div>
          )}
          {tab === "studio" && (
            <>
              <div className="studio-grid">
                <section className="editor-column">
                  <div className="panel media-panel">
                    <div className="section-title">
                      <span className="number">01</span>
                      <h2>Seus arquivos</h2>
                      <span className="hint">Vídeo + nova faixa de áudio</span>
                    </div>
                    <div className="import-grid">
                      <button
                        className={`import-box ${video ? "filled" : ""}`}
                        onClick={() => void pick("video")}
                        disabled={busy}
                      >
                        <span className="import-icon">
                          <Film size={25} />
                        </span>
                        <strong>
                          {video ? video.name : "Adicionar vídeo"}
                        </strong>
                        <small>
                          {video
                            ? `${video.width} × ${video.height} · ${duration(video.duration)}`
                            : "Arraste sua ideia para uma nova voz"}
                        </small>
                        <span className="format">
                          {video ? "TROCAR ARQUIVO" : "MP4, MOV"}{" "}
                          <Plus size={13} />
                        </span>
                      </button>
                      <button
                        className={`import-box audio ${audio ? "filled" : ""}`}
                        onClick={() => void pick("audio")}
                        disabled={busy}
                      >
                        <span className="import-icon">
                          <AudioLines size={25} />
                        </span>
                        <strong>
                          {audio ? audio.name : "Adicionar áudio"}
                        </strong>
                        <small>
                          {audio
                            ? `${duration(audio.duration)} · faixa de voz`
                            : "A voz que vai transformar o vídeo"}
                        </small>
                        <span className="format">
                          {audio ? "TROCAR ARQUIVO" : "MP3, WAV"}{" "}
                          <Plus size={13} />
                        </span>
                      </button>
                    </div>
                    {media.length > 0 && (
                      <div className="existing-media">
                        <label>
                          Vídeos importados
                          <select
                            value={videoId}
                            onChange={(e) => setVideoId(e.target.value)}
                          >
                            <option value="">Selecionar vídeo</option>
                            {media
                              .filter((m) => m.kind === "video")
                              .map((m) => (
                                <option key={m.id} value={m.id}>
                                  {m.name}
                                </option>
                              ))}
                          </select>
                        </label>
                        <label>
                          Áudios importados
                          <select
                            value={audioId}
                            onChange={(e) => setAudioId(e.target.value)}
                          >
                            <option value="">Selecionar áudio</option>
                            {media
                              .filter((m) => m.kind === "audio")
                              .map((m) => (
                                <option key={m.id} value={m.id}>
                                  {m.name}
                                </option>
                              ))}
                          </select>
                        </label>
                      </div>
                    )}
                  </div>
                  <div className="panel viewer-panel">
                    <div className="section-title">
                      <span className="number">02</span>
                      <h2>Visualização</h2>
                      <div className="segmented">
                        <button
                          className={!comparison ? "selected" : ""}
                          onClick={() => setComparison(false)}
                        >
                          Original
                        </button>
                        <button
                          className={comparison ? "selected" : ""}
                          onClick={() => setComparison(true)}
                          disabled={!current?.output}
                        >
                          Comparar A/B
                        </button>
                      </div>
                    </div>
                    <div className={`viewer ${comparison ? "ab" : ""}`}>
                      {comparison && current?.output ? (
                        <>
                          <div>
                            <span className="video-label">A · ORIGINAL</span>
                            <video
                              ref={originalRef}
                              src={mediaUrl(current.video_id!)}
                              muted
                              playsInline
                            />
                          </div>
                          <div>
                            <span className="video-label">
                              B · {names[current.model]}
                            </span>
                            <video
                              ref={resultRef}
                              src={resultUrl(current.id)}
                              controls
                              playsInline
                              onPlay={sync}
                              onPause={sync}
                              onSeeked={sync}
                              onTimeUpdate={sync}
                            />
                          </div>
                        </>
                      ) : video ? (
                        <video src={mediaUrl(video.id)} controls playsInline />
                      ) : (
                        <div className="viewer-empty">
                          <div className="focus-corners">
                            <ScanFace size={46} strokeWidth={1} />
                          </div>
                          <h3>Seu próximo resultado começa aqui</h3>
                          <p>
                            Importe um vídeo e uma faixa de voz para começar.
                          </p>
                          <button
                            className="secondary"
                            onClick={() => void pick("video")}
                            disabled={busy}
                          >
                            <FolderOpen size={15} /> Escolher vídeo
                          </button>
                        </div>
                      )}
                    </div>
                    <div className="viewer-bottom">
                      <span>
                        <MonitorPlay size={14} />
                        {video
                          ? `${video.width} × ${video.height} · ${video.fps} FPS`
                          : "Nenhum vídeo selecionado"}
                      </span>
                      <span>Composição facial original</span>
                    </div>
                  </div>
                  <div className="quality-note">
                    <ShieldCheck size={18} />
                    <div>
                      <strong>A identidade vem primeiro.</strong>
                      <span>
                        Sem restauração facial agressiva automática. Região
                        facial composta pelos motores oficiais.
                      </span>
                    </div>
                  </div>
                </section>
                <aside className="settings-column">
                  <div className="panel settings-panel">
                    <div className="section-title">
                      <Sparkles size={17} className="lime" />
                      <h2>Configuração de render</h2>
                    </div>
                    <label className="field-label">
                      Motor de IA <span className="tiny-tag">3 MODELOS</span>
                    </label>
                    <div className="model-select">
                      <select
                        value={automatic ? "auto" : model}
                        onChange={(e) => {
                          setAutomatic(e.target.value === "auto");
                          if (e.target.value !== "auto")
                            setModel(e.target.value);
                        }}
                      >
                        <option value="auto">Automático · recomendado</option>
                        {Object.entries(names).map(([id, name]) => (
                          <option key={id} value={id}>
                            {name}
                          </option>
                        ))}
                      </select>
                      <ChevronDown size={15} />
                    </div>
                    <div className="model-description">
                      <Cpu size={15} />
                      <span>
                        {automatic
                          ? hw?.recommendation
                            ? `${names[hw.recommendation]} pela VRAM livre`
                            : "Aguardando GPU compatível"
                          : `${names[model]} · seleção manual`}
                      </span>
                    </div>
                    <div className="field-label preset-label">
                      Preset de qualidade
                    </div>
                    <div className="presets">
                      {[
                        {
                          id: "fast",
                          name: "Fast",
                          desc: "Mais velocidade",
                          icon: Zap,
                        },
                        {
                          id: "balanced",
                          name: "Balanced",
                          desc: "O melhor equilíbrio",
                          icon: Activity,
                        },
                        {
                          id: "quality",
                          name: "Quality",
                          desc: "Mais refinamento",
                          icon: Sparkles,
                        },
                      ].map((p) => (
                        <button
                          key={p.id}
                          className={
                            preset === p.id ? "preset chosen" : "preset"
                          }
                          onClick={() => {
                            setPreset(p.id);
                            setSteps(
                              p.id === "fast"
                                ? 20
                                : p.id === "quality"
                                  ? 50
                                  : 30,
                            );
                            setBatch(
                              p.id === "fast" ? 8 : p.id === "quality" ? 2 : 4,
                            );
                          }}
                        >
                          <p.icon size={16} />
                          <strong>{p.name}</strong>
                          <small>{p.desc}</small>
                        </button>
                      ))}
                    </div>
                    <div className="settings-divider" />
                    <div className="field-label">
                      Prévia de trecho{" "}
                      <span className="muted-text">em segundos</span>
                    </div>
                    <div className="input-row">
                      <label>
                        Início
                        <input
                          type="number"
                          min="0"
                          step="0.1"
                          value={start}
                          onChange={(e) => setStart(Number(e.target.value))}
                        />
                      </label>
                      <label>
                        Duração
                        <select
                          value={seconds}
                          onChange={(e) => setSeconds(Number(e.target.value))}
                        >
                          {[3, 5, 10, 15].map((n) => (
                            <option key={n} value={n}>
                              {n} segundos
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <button
                      className="advanced-toggle"
                      onClick={() => setAdvanced(!advanced)}
                    >
                      <Settings2 size={15} /> Parâmetros avançados{" "}
                      <ChevronDown
                        size={14}
                        style={{ transform: advanced ? "rotate(180deg)" : "" }}
                      />
                    </button>
                    {advanced && (
                      <div className="advanced">
                        {model.startsWith("latent") ? (
                          <>
                            <label>
                              Passos de inferência
                              <input
                                type="number"
                                min={20}
                                max={50}
                                value={steps}
                                onChange={(e) => setSteps(+e.target.value)}
                              />
                            </label>
                            <label>
                              Guidance (1–3)
                              <input
                                type="number"
                                min={1}
                                max={3}
                                step={0.1}
                                value={guidance}
                                onChange={(e) => setGuidance(+e.target.value)}
                              />
                            </label>
                            <label>
                              Seed
                              <input
                                type="number"
                                min={0}
                                value={seed}
                                onChange={(e) => setSeed(+e.target.value)}
                              />
                            </label>
                          </>
                        ) : (
                          <>
                            <label>
                              Batch size
                              <input
                                type="number"
                                min={1}
                                max={16}
                                value={batch}
                                onChange={(e) => setBatch(+e.target.value)}
                              />
                            </label>
                            <label>
                              Margem facial
                              <input
                                type="number"
                                min={0}
                                max={40}
                                value={margin}
                                onChange={(e) => setMargin(+e.target.value)}
                              />
                            </label>
                            <label>
                              Largura da máscara
                              <input
                                type="number"
                                min={20}
                                max={150}
                                value={cheek}
                                onChange={(e) => setCheek(+e.target.value)}
                              />
                            </label>
                            <label>
                              Composição
                              <select
                                value={parsing}
                                onChange={(e) => setParsing(e.target.value)}
                              >
                                <option value="jaw">Jaw</option>
                                <option value="neck">Neck</option>
                                <option value="raw">Raw</option>
                              </select>
                            </label>
                          </>
                        )}
                      </div>
                    )}
                    <div className="export-summary">
                      <div>
                        <span>Formato de saída</span>
                        <strong>MP4 · H.264</strong>
                      </div>
                      <div>
                        <span>Resolução</span>
                        <strong>
                          {video
                            ? `${video.width} × ${video.height}`
                            : "Original"}
                        </strong>
                      </div>
                      <div>
                        <span>Restauração facial</span>
                        <strong>Desativada</strong>
                      </div>
                    </div>
                    <button
                      className="secondary wide"
                      disabled={!canRender}
                      onClick={() => void render(true)}
                    >
                      <Play size={15} /> Renderizar prévia{" "}
                      <span>{seconds}s</span>
                    </button>
                    <button
                      className="primary wide"
                      disabled={!canRender}
                      onClick={() => void render(false)}
                    >
                      {busy ? (
                        <LoaderCircle size={17} className="spin" />
                      ) : (
                        <Sparkles size={17} />
                      )}{" "}
                      Adicionar à fila <ArrowRight size={17} />
                    </button>
                    <p className="render-hint">
                      {!engine?.ready
                        ? "Instale um modelo para habilitar a renderização."
                        : "A duração final acompanha a menor faixa de entrada."}
                    </p>
                  </div>
                  <div className="tip-card">
                    <span className="eyebrow">UM BOM COMEÇO</span>
                    <h3>Voz limpa. Rosto visível.</h3>
                    <p>
                      Use áudio sem música e um rosto frontal, bem iluminado,
                      para ajudar a sincronização.
                    </p>
                    <span>Qualidade depende da entrada e do modelo.</span>
                  </div>
                </aside>
              </div>
              <section className="queue-strip">
                <div>
                  <ListVideo size={19} />
                  <strong>Fila de processamento</strong>
                  <span>{active.length} pendentes</span>
                </div>
                <button onClick={() => setTab("queue")}>
                  Ver todos os trabalhos <ArrowRight size={15} />
                </button>
              </section>
              {current && (
                <JobRow
                  job={current}
                  selected={true}
                  onSelect={() => setTab("queue")}
                  onCancel={() =>
                    void action(() => api(`/jobs/${current.id}/cancel`, {}))
                  }
                  onExport={() => void exportVideo(current)}
                />
              )}
            </>
          )}
          {tab === "models" && (
            <>
              <div className="notice">
                <ShieldCheck size={18} />
                <span>
                  Revise <code>docs/MODELS.md</code> e as licenças dos pesos
                  auxiliares. InsightFace não autoriza uso comercial dos pesos
                  por padrão.
                </span>
              </div>
              <label className="license-checkbox">
                <input
                  type="checkbox"
                  checked={reviewed}
                  onChange={(e) => setReviewed(e.target.checked)}
                />{" "}
                Revisei as licenças e os requisitos aplicáveis ao meu uso.
              </label>
              <div className="model-grid">
                {Object.entries(names).map(([id, name]) => {
                  const m = models.find((x) => x.id === id);
                  return (
                    <article className="panel model-card" key={id}>
                      <span className="model-glyph">
                        <Layers3 size={24} />
                      </span>
                      <span className={`status ${m?.ready ? "completed" : ""}`}>
                        {m?.ready ? "Verificado" : "Não verificado"}
                      </span>
                      <h2>{name}</h2>
                      <p>
                        {id === "musetalk-1.5"
                          ? "Inferência em uma etapa e composição com máscara facial."
                          : "Difusão temporal com alinhamento facial e recomposição dos frames."}
                      </p>
                      <div className="model-facts">
                        <span>
                          {id === "latentsync-1.6" ? "512 × 512" : "256 × 256"}{" "}
                          face
                        </span>
                        <span>
                          {id === "latentsync-1.6"
                            ? "18 GB"
                            : id === "latentsync-1.5"
                              ? "8 GB"
                              : "~6 GB"}{" "}
                          VRAM
                        </span>
                      </div>
                      <p className="license-text">
                        {m?.license ??
                          "Conecte o backend para consultar requisitos."}
                      </p>
                      <button
                        className="text-button"
                        onClick={() =>
                          void action(async () =>
                            setPreflight({
                              id,
                              ...(await api<{
                                issues: string[];
                                license: string;
                              }>(`/models/${id}/preflight`)),
                            }),
                          )
                        }
                        disabled={!online}
                      >
                        Verificar compatibilidade <ArrowRight size={14} />
                      </button>
                      <div className="model-actions">
                        <button
                          className="secondary"
                          disabled={!online || !reviewed || busy}
                          onClick={() => void install(id, "install")}
                        >
                          <Cpu size={15} />
                          {m?.environment_installed
                            ? "Reparar modelo"
                            : "Instalar modelo"}
                        </button>
                        <button
                          className="secondary"
                          disabled={
                            !m?.environment_installed || !reviewed || busy
                          }
                          onClick={() => void install(id, "checkpoints")}
                        >
                          <ArrowDownToLine size={15} />
                          {m?.checkpoints_installed
                            ? "Verificar checkpoints"
                            : "Baixar checkpoints"}
                        </button>
                        <button
                          className="text-button danger"
                          disabled={!online || busy}
                          onClick={() => {
                            if (
                              window.confirm(
                                `Remover ambiente e checkpoints de ${name}?`,
                              )
                            )
                              void install(id, "remove");
                          }}
                        >
                          Remover modelo
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
              {preflight && (
                <div className="panel preflight">
                  <h3>{names[preflight.id]} · Compatibilidade</h3>
                  {preflight.issues.length ? (
                    preflight.issues.map((i) => <p key={i}>• {i}</p>)
                  ) : (
                    <p>
                      Pré-requisitos detectados. CUDA/PyTorch será validado no
                      ambiente isolado.
                    </p>
                  )}
                  <small>{preflight.license}</small>
                </div>
              )}
            </>
          )}
          {tab === "queue" && (
            <>
              <div className="panel jobs-panel">
                <div className="section-title">
                  <ListVideo size={18} />
                  <h2>Trabalhos</h2>
                  <span className="hint">
                    {jobs.length} no histórico · execução serial
                  </span>
                </div>
                {jobs.length ? (
                  jobs.map((j) => (
                    <JobRow
                      key={j.id}
                      job={j}
                      selected={selected === j.id}
                      onSelect={() => {
                        setSelected(j.id);
                        if (j.output) {
                          setVideoId(j.video_id ?? "");
                        }
                      }}
                      onCancel={() =>
                        void action(() => api(`/jobs/${j.id}/cancel`, {}))
                      }
                      onExport={() => void exportVideo(j)}
                    />
                  ))
                ) : (
                  <div className="empty-jobs">
                    <ListVideo size={34} />
                    <h3>Sua fila está livre</h3>
                    <p>
                      Renderizações e instalações aparecerão aqui quando forem
                      iniciadas.
                    </p>
                    <button
                      className="secondary"
                      onClick={() => setTab("studio")}
                    >
                      Ir para o estúdio <ArrowRight size={15} />
                    </button>
                  </div>
                )}
              </div>
              {current?.output && (
                <button
                  className="secondary compare-button"
                  onClick={() => {
                    setComparison(true);
                    setTab("studio");
                  }}
                >
                  <MonitorPlay size={16} /> Comparar original e resultado
                </button>
              )}
              <div className="panel logs-panel">
                <div className="section-title">
                  <Terminal size={17} />
                  <h2>Logs do processo</h2>
                  <span className="hint">
                    {selected?.slice(0, 8) ?? "Selecione um trabalho"}
                  </span>
                </div>
                <pre>{logs || "Aguardando saída do processo selecionado."}</pre>
              </div>
            </>
          )}
          {tab === "system" && (
            <div className="panel system-panel">
              <div className="section-title">
                <Cpu size={18} />
                <h2>Diagnóstico em tempo real</h2>
              </div>
              <dl>
                <dt>Backend</dt>
                <dd>
                  {online
                    ? "Conectado · API local autenticada"
                    : "Desconectado"}
                </dd>
                <dt>Sistema de inferência</dt>
                <dd>{hw?.platform ?? "Indisponível"}</dd>
                <dt>FFmpeg / FFprobe</dt>
                <dd>
                  {hw
                    ? `${hw.ffmpeg ? "OK" : "Ausente"} / ${hw.ffprobe ? "OK" : "Ausente"}`
                    : "Indisponível"}
                </dd>
                <dt>GPU</dt>
                <dd>
                  {hw?.gpus
                    .map(
                      (g) =>
                        `${g.name} · driver ${g.driver} · ${(g.free_mb / 1024).toFixed(1)} GB livres`,
                    )
                    .join(", ") || "NVIDIA não detectada"}
                </dd>
                <dt>Recomendação</dt>
                <dd>
                  {hw?.recommendation
                    ? names[hw.recommendation]
                    : "Nenhum modelo compatível detectado"}
                </dd>
              </dl>
              {hw?.error && <p className="error-text">{hw.error}</p>}
              <p>
                O diagnóstico definitivo de CUDA e das dependências é executado
                dentro de cada ambiente Python durante a instalação. Nenhum
                teste de qualidade visual é substituído por esta detecção.
              </p>
              <button className="secondary" onClick={() => void refresh()}>
                Atualizar diagnóstico
              </button>
            </div>
          )}
          <footer>
            <span>
              <AudioLines size={13} /> MIMISYNC <b>LOCAL STUDIO</b>
            </span>
            <span>Seus modelos. Seus arquivos. Seu controle.</span>
            <span>v0.2.0 · teste</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
function JobRow({
  job,
  selected,
  onSelect,
  onCancel,
  onExport,
}: {
  job: Job;
  selected: boolean;
  onSelect: () => void;
  onCancel: () => void;
  onExport: () => void;
}) {
  return (
    <div className={`job-row ${selected ? "selected-job" : ""}`}>
      <button className="job-main" onClick={onSelect}>
        <span className="job-icon">
          {job.status === "running" ? (
            <LoaderCircle className="spin" size={19} />
          ) : job.status === "completed" ? (
            <Check size={19} />
          ) : (
            <Film size={19} />
          )}
        </span>
        <div>
          <strong>
            {names[job.model] ?? job.model}{" "}
            <small>
              {job.kind === "render"
                ? job.preview
                  ? "Prévia"
                  : "Renderização"
                : job.kind === "install"
                  ? "Instalação do modelo"
                  : job.kind === "environment"
                  ? "Ambiente Python"
                  : job.kind === "remove"
                    ? "Remoção"
                    : "Checkpoints"}
            </small>
          </strong>
          <span>{job.stage}</span>
        </div>
      </button>
      <span className={`status ${job.status}`}>
        {job.status === "running"
          ? job.progress === null
            ? "Em execução"
            : `${job.progress}% · etapa`
          : ({
              queued: "Na fila",
              completed: "Concluído",
              failed: "Falhou",
              cancelled: "Cancelado",
              interrupted: "Interrompido",
            }[job.status] ?? job.status)}
      </span>
      {["running", "queued"].includes(job.status) && (
        <button className="icon-button" title="Cancelar" onClick={onCancel}>
          <Square size={14} />
        </button>
      )}
      {job.output && job.status === "completed" && (
        <button className="secondary" onClick={onExport}>
          <ArrowDownToLine size={14} /> Exportar
        </button>
      )}
    </div>
  );
}
