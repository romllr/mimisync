import { invoke, isTauri } from "@tauri-apps/api/core";
export const desktop = isTauri();
export interface Media {
  id: string;
  name: string;
  kind: "video" | "audio";
  duration: number;
  width: number | null;
  height: number | null;
  fps: string;
  vfr: boolean;
}
export interface Model {
  id: string;
  name: string;
  min_vram_mb: number;
  face_resolution: number;
  license: string;
  repository: string;
  commit: string;
  checkpoint_repo: string;
  environment_installed: boolean;
  checkpoints_installed: boolean;
  ready: boolean;
}
export interface Job {
  id: string;
  kind: string;
  model: string;
  status: string;
  stage: string;
  progress: number | null;
  created_at: string;
  output?: string;
  video_id?: string;
  start?: number;
  duration?: number;
  preview?: boolean;
}
export interface Hardware {
  platform: string;
  gpus: {
    index: number;
    name: string;
    total_mb: number;
    free_mb: number;
    driver: string;
  }[];
  ffmpeg: boolean;
  ffprobe: boolean;
  recommendation: string | null;
  error: string | null;
}
export const api = <T>(path: string, body?: unknown): Promise<T> =>
  desktop
    ? invoke("api", {
        method: body === undefined ? "GET" : "POST",
        path,
        body: body ?? null,
      })
    : Promise.reject(
        new Error("Abra o aplicativo desktop para conectar ao backend local."),
      );
export const importMedia = (path: string): Promise<Media> =>
  invoke("import_media", { path });
export const connection = (): Promise<{ url: string; token: string }> =>
  invoke("connection");
export const exportResult = (id: string, path: string) =>
  invoke("export_result", { id, path });
