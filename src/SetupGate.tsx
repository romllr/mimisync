import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  AudioLines,
  Check,
  ChevronDown,
  Download,
  LoaderCircle,
  Monitor,
  ShieldCheck,
  Sparkles,
  Terminal,
} from "lucide-react";
import { desktop } from "./api";
interface Setup {
  busy: boolean;
  phase: string;
  wsl_available: boolean;
  runtime_installed: boolean;
  gpu: string | null;
  error: string | null;
  logs: string[];
  downloaded: number;
  total: number | null;
}
const labels: Record<string, string> = {
  checking: "Verificando seu computador",
  needs_windows: "Precisamos habilitar um componente do Windows",
  needs_runtime: "Vamos preparar seu estúdio",
  download: "Baixando o ambiente de processamento",
  import: "Criando o ambiente do Mimisync",
  install: "Instalando os componentes locais",
  ready: "Conectando ao seu estúdio",
  development: "Abrindo o estúdio",
  windows: "Aguardando a autorização do Windows",
  restart: "Uma etapa do Windows foi concluída",
  error: "A preparação precisa de atenção",
};
const text = (error: unknown) =>
  error instanceof Error ? error.message : String(error);
export default function SetupGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Setup | null>(null),
    [ready, setReady] = useState(!desktop),
    [error, setError] = useState(""),
    [starting, setStarting] = useState(false),
    [copied, setCopied] = useState(false);
  const connecting = useRef(false),
    inspected = useRef(false);
  const poll = useCallback(async () => {
    if (desktop) {
      try {
        setStatus(await invoke<Setup>("setup_status"));
      } catch (e) {
        setError(text(e));
      }
    }
  }, []);
  useEffect(() => {
    if (!desktop) return;
    if (!inspected.current) {
      inspected.current = true;
      void invoke("setup_inspect")
        .then(poll)
        .catch((e) => setError(text(e)));
    }
    const timer = setInterval(() => void poll(), 1000);
    void poll();
    return () => clearInterval(timer);
  }, [poll]);
  const connect = useCallback(async () => {
    if (connecting.current) return;
    connecting.current = true;
    setError("");
    setStarting(true);
    try {
      await invoke("backend_start");
      setReady(true);
    } catch (e) {
      setError(text(e));
    } finally {
      connecting.current = false;
      setStarting(false);
    }
  }, []);
  useEffect(() => {
    if (status?.runtime_installed && !status.busy) void connect();
  }, [status?.runtime_installed, status?.busy, connect]);
  async function run(command: string) {
    setError("");
    try {
      await invoke(command);
      await poll();
    } catch (e) {
      setError(text(e));
    }
  }
  if (ready) return <>{children}</>;
  const busy = !!status?.busy || starting;
  const detail = [error, status?.error, ...(status?.logs ?? [])]
    .filter(Boolean)
    .join("\n");
  const failed = !!error || !!status?.error;
  return (
    <div className="setup-page">
      <div className="setup-brand">
        <span className="brand-icon">
          <AudioLines size={23} />
        </span>
        mimisync <span>PRIMEIRA ABERTURA</span>
      </div>
      <section className="setup-card">
        <div className="setup-hero">
          <div className="setup-glyph">
            {busy ? (
              <LoaderCircle size={34} className="spin" />
            ) : (
              <Sparkles size={34} />
            )}
          </div>
          <div className="eyebrow">SEU ESTÚDIO. NA SUA MÁQUINA.</div>
          <h1>
            {starting
              ? "Abrindo seu estúdio"
              : (labels[status?.phase ?? "checking"] ??
                "Preparando seu estúdio")}
          </h1>
          <p>
            O Mimisync cuida da instalação para você. Sem terminal, sem
            configurar Python e sem copiar comandos.
          </p>
        </div>
        <div className="setup-steps">
          {[
            {
              name: "Componentes do Windows",
              icon: Monitor,
              done: status?.wsl_available,
            },
            {
              name: "Processamento local",
              icon: Download,
              done: status?.runtime_installed,
            },
            {
              name: "Estúdio pronto para seus modelos",
              icon: Sparkles,
              done: false,
            },
          ].map((step, i) => (
            <div
              key={step.name}
              className={step.done ? "setup-step done" : "setup-step"}
            >
              <span>
                {step.done ? <Check size={17} /> : <step.icon size={17} />}
              </span>
              <strong>{step.name}</strong>
              <small>{step.done ? "Verificado" : `${i + 1} de 3`}</small>
            </div>
          ))}
        </div>
        {status?.gpu && (
          <div className="setup-hardware">
            <ShieldCheck size={16} /> GPU detectada: {status.gpu}
          </div>
        )}
        {status?.phase === "download" && (
          <div className="setup-download">
            <div>
              <span>
                {(status.downloaded / 1024 ** 2).toFixed(1)} MB baixados
              </span>
              <span>
                {status.total
                  ? `${(status.total / 1024 ** 2).toFixed(0)} MB no total`
                  : "Tamanho total ainda não informado"}
              </span>
            </div>
            {status.total && (
              <progress value={status.downloaded} max={status.total} />
            )}
          </div>
        )}
        {failed && (
          <div className="alert">
            <div>
              <strong>Não foi possível concluir esta etapa.</strong>
              <p>
                Tente novamente. Se continuar, copie os detalhes abaixo para nos
                enviar.
              </p>
            </div>
          </div>
        )}
        {!busy && status && !status.runtime_installed && (
          <>
            <div className="setup-explainer">
              <ShieldCheck size={19} />
              <p>
                Será criado um ambiente exclusivo do Mimisync. A primeira
                preparação usa internet e alguns GB de disco. Os modelos de IA
                são escolhidos e baixados dentro do app depois. Seus vídeos
                continuam na sua máquina.
              </p>
            </div>
            {!status.wsl_available ? (
              <>
                <button
                  className="primary setup-action"
                  onClick={() => void run("setup_windows")}
                >
                  <Monitor size={17} /> Habilitar componentes do Windows
                </button>
                <small className="setup-footnote">
                  O Windows pode pedir autorização de administrador e uma
                  reinicialização. O app não reinicia seu computador sozinho.
                </small>
                <button
                  className="text-button"
                  onClick={() => void run("setup_inspect")}
                >
                  Já habilitei ou reiniciei · verificar novamente
                </button>
              </>
            ) : (
              <>
                <button
                  className="primary setup-action"
                  onClick={() => void run("setup_prepare")}
                >
                  <Download size={17} />
                  {failed
                    ? "Tentar preparar novamente"
                    : "Instalar componentes necessários"}
                </button>
                <small className="setup-footnote">
                  Ubuntu oficial com checksum verificado. Nenhuma instalação
                  pessoal do Ubuntu será alterada.
                </small>
              </>
            )}
          </>
        )}
        {!busy && status?.runtime_installed && failed && (
          <>
            <button
              className="primary setup-action"
              onClick={() => void connect()}
            >
              Tentar abrir o estúdio
            </button>
            <button
              className="text-button"
              onClick={() => void run("setup_prepare")}
            >
              Reparar componentes locais
            </button>
          </>
        )}
        {busy && (
          <div className="setup-wait">
            <LoaderCircle size={17} className="spin" />
            <span>
              {starting
                ? "Conectando ao processador local…"
                : status?.logs.at(-1)?.slice(0, 150) ||
                  "Aguarde a conclusão desta etapa…"}
            </span>
          </div>
        )}
        <details className="setup-details">
          <summary>
            <Terminal size={15} /> Detalhes da preparação{" "}
            <ChevronDown size={14} />
          </summary>
          <pre>{detail || "Aguardando diagnóstico do computador."}</pre>
          <button
            className="secondary"
            onClick={() =>
              void navigator.clipboard
                .writeText(detail)
                .then(() => setCopied(true))
                .catch(() =>
                  setError(
                    "Não foi possível copiar. Selecione os detalhes e copie.",
                  ),
                )
            }
          >
            {copied ? "Detalhes copiados" : "Copiar detalhes"}
          </button>
        </details>
      </section>
      <p className="setup-bottom">Windows 11 x64 · IA local · Sem APIs pagas</p>
    </div>
  );
}
