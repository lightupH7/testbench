export type ScopeMode = "mock" | "api";

export type ScopeDriverResult<T = unknown> = {
  success: boolean;
  message?: string;
  data?: T;
  stdout?: string;
  stderr?: string;
  returncode?: number | null;
};

export type ScopeConnectionPayload = {
  ip: string;
  port: number;
  timeout_ms: number;
};

export type ScopeChannelPayload = ScopeConnectionPayload & {
  channel: string;
  enabled: boolean;
  scale: number;
  offset: number;
  coupling: string;
};

export type ScopeMeasurePayload = ScopeConnectionPayload & {
  channel: string;
  measure: string;
  expected?: {
    min?: number;
    max?: number;
  };
};

export type ScopeWaveformPayload = ScopeConnectionPayload & {
  channel: string;
  points: number;
  preview_points: number;
  waveform_format: string;
  binary: boolean;
  datatype: string;
};

export type ScopeWaveformSample = {
  x: number;
  y: number;
};

export type ScopeWaveformData = {
  channel?: string;
  format?: string;
  encoding?: string;
  points?: number;
  preview_points?: number;
  x_unit?: string;
  y_unit?: string;
  samples?: ScopeWaveformSample[];
  preview?: number[];
  command?: string;
  setup_commands?: string[];
};

export async function detectScope(payload: ScopeConnectionPayload) {
  return postScope("/api/scope/idn", payload);
}

export async function setScopeChannel(payload: ScopeChannelPayload) {
  return postScope("/api/scope/channel", payload);
}

export async function measureScope(payload: ScopeMeasurePayload) {
  return postScope("/api/scope/measure", payload);
}

export async function readScopeWaveform(payload: ScopeWaveformPayload) {
  return postScope<ScopeWaveformData>("/api/scope/waveform", payload);
}

async function postScope<T>(
  url: string,
  payload: Record<string, unknown>
): Promise<ScopeDriverResult<T>> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  let result: ScopeDriverResult<T>;
  try {
    result = (await response.json()) as ScopeDriverResult<T>;
  } catch {
    result = {
      success: false,
      message: `HTTP ${response.status}`,
      stderr: "Failed to parse backend response."
    };
  }

  if (!response.ok) {
    const detail =
      result.stderr?.trim() ||
      result.message ||
      (url.endsWith("/waveform")
        ? "后端波形接口暂不可用，请使用 Mock Mode 或先实现后端。"
        : `HTTP ${response.status}`);
    throw new Error(detail);
  }

  return result;
}
