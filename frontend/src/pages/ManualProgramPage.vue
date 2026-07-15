<template>
  <q-page class="page">
    <section class="page-section">
      <div class="section-head">
        <div class="section-kicker">Manual Programming</div>
        <h1 class="section-title">Hand Program FPGA Files</h1>
      </div>

      <div class="manual-grid">
        <section class="surface-block">
          <div class="block-head">
            <h2 class="block-title">Action</h2>
            <q-btn
              flat
              round
              icon="health_and_safety"
              color="primary"
              :loading="isCheckingHealth"
              @click="checkHealth"
            >
              <q-tooltip>Check backend</q-tooltip>
            </q-btn>
          </div>

          <q-btn-toggle
            v-model="form.action"
            class="action-switch"
            no-caps
            spread
            unelevated
            toggle-color="primary"
            text-color="grey-8"
            :options="actionOptions"
          />

          <div class="form-grid">
            <q-select
              v-if="needsBit"
              v-model="form.bit_file"
              outlined
              dense
              emit-value
              map-options
              use-input
              fill-input
              hide-selected
              input-debounce="0"
              clearable
              label="Bit File"
              :options="filteredBitOptions"
              :display-value="selectedFileName(form.bit_file)"
              @filter="filterBitOptions"
            />

            <q-select
              v-if="needsElf"
              v-model="form.elf_file"
              outlined
              dense
              emit-value
              map-options
              use-input
              fill-input
              hide-selected
              input-debounce="0"
              clearable
              label="ELF File"
              :options="filteredElfOptions"
              :display-value="selectedFileName(form.elf_file)"
              @filter="filterElfOptions"
            />

            <q-input
              v-if="needsBit"
              v-model="form.vivado_path"
              outlined
              dense
              label="Vivado"
              placeholder="vivado"
            />

            <q-input
              v-if="needsBit"
              v-model="form.hw_server_url"
              outlined
              dense
              clearable
              label="HW Server"
              placeholder="localhost:3121"
            />

            <q-input
              v-if="needsElf"
              v-model="form.device"
              outlined
              dense
              clearable
              label="Device"
              placeholder="RISC-V"
            />

            <q-select
              v-if="needsElf"
              v-model="form.interface"
              outlined
              dense
              emit-value
              map-options
              label="Interface"
              :options="interfaceOptions"
            />

            <q-input
              v-if="needsElf"
              v-model.number="form.speed"
              type="number"
              outlined
              dense
              label="Speed"
            />

            <q-input
              v-model.number="form.timeout"
              type="number"
              outlined
              dense
              label="Timeout"
            />
          </div>

          <div class="button-row">
            <q-btn
              flat
              round
              icon="refresh"
              color="grey-8"
              :loading="isLoadingFiles"
              @click="loadFileOptions"
            >
              <q-tooltip>Refresh file list</q-tooltip>
            </q-btn>
            <q-btn
              color="primary"
              text-color="white"
              unelevated
              no-caps
              icon="play_arrow"
              :loading="isSubmitting"
              :disable="!canSubmit"
              :label="submitLabel"
              @click="submitManualAction"
            />
            <q-btn
              flat
              round
              icon="content_copy"
              color="grey-8"
              @click="copyPayload"
            >
              <q-tooltip>Copy payload</q-tooltip>
            </q-btn>
            <q-btn
              flat
              round
              icon="delete_sweep"
              color="grey-8"
              @click="clearResult"
            >
              <q-tooltip>Clear result</q-tooltip>
            </q-btn>
          </div>
        </section>

        <section class="surface-block">
          <div class="block-head">
            <h2 class="block-title">Result</h2>
            <div class="block-head__badges">
              <q-badge
                rounded
                :color="streamConnected ? 'positive' : 'grey-6'"
                text-color="white"
                :label="streamConnected ? 'Live Stream On' : 'Live Stream Off'"
              />
              <q-badge
                rounded
                :color="resultTone.color"
                text-color="white"
                :label="resultTone.label"
              />
            </div>
          </div>

          <div class="status-line" :class="`status-line--${resultTone.state}`">
            {{ statusMessage }}
          </div>

          <q-linear-progress
            v-if="isSubmitting"
            indeterminate
            color="primary"
            class="execution-progress"
          />

          <div v-if="isSubmitting" class="execution-note">
            Execution is in progress. Live Vivado and J-Link output will stream
            into the tabs below.
          </div>

          <div class="step-stack">
            <article class="step-item">
              <div class="step-item__head">
                <strong>Bit</strong>
                <q-icon
                  :name="stepIcon(stepBit)"
                  :color="stepColor(stepBit)"
                  size="20px"
                />
              </div>
              <div class="step-item__body">{{
                stepMessage(stepBit, needsBit)
              }}</div>
            </article>

            <article class="step-item">
              <div class="step-item__head">
                <strong>ELF</strong>
                <q-icon
                  :name="stepIcon(stepElf)"
                  :color="stepColor(stepElf)"
                  size="20px"
                />
              </div>
              <div class="step-item__body">{{
                stepMessage(stepElf, needsElf)
              }}</div>
            </article>
          </div>

          <q-tabs
            v-model="activeTab"
            dense
            active-color="primary"
            indicator-color="primary"
            no-caps
          >
            <q-tab name="stdout" label="Stdout" />
            <q-tab name="stderr" label="Stderr" />
            <q-tab name="json" label="JSON" />
          </q-tabs>

          <q-tab-panels v-model="activeTab" animated class="log-tabs">
            <q-tab-panel name="stdout" class="log-tabs__panel">
              <pre class="log-console">{{ stdoutText }}</pre>
            </q-tab-panel>
            <q-tab-panel name="stderr" class="log-tabs__panel">
              <pre class="log-console log-console--error">{{ stderrText }}</pre>
            </q-tab-panel>
            <q-tab-panel name="json" class="log-tabs__panel">
              <pre class="log-console">{{ jsonText }}</pre>
            </q-tab-panel>
          </q-tab-panels>
        </section>
      </div>
    </section>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { copyToClipboard, useQuasar } from "quasar";

type ManualAction = "program_bit" | "program_elf" | "program_all";
type LogTab = "stdout" | "stderr" | "json";
type SelectOption = { label: string; value: string };

type DriverResult = {
  success: boolean;
  message: string;
  data: unknown;
  stdout: string;
  stderr: string;
  returncode: number | null;
};

type ManualResponse = DriverResult & {
  data?: {
    bit_result?: DriverResult | null;
    elf_result?: DriverResult | null;
  } | null;
};

const $q = useQuasar();

const actionOptions = [
  { label: "Only Bit", value: "program_bit" },
  { label: "Only ELF", value: "program_elf" },
  { label: "Bit Then ELF", value: "program_all" }
];

const interfaceOptions = [
  { label: "JTAG", value: "JTAG" },
  { label: "SWD", value: "SWD" }
];

const form = reactive({
  action: "program_all" as ManualAction,
  bit_file: "artifacts/bitstreams/lowrisc_systems_chip.bit",
  elf_file: "artifacts/firmware/zephyr-it.elf",
  vivado_path: "vivado",
  hw_server_url: "localhost:3121",
  device: "RISC-V",
  interface: "JTAG",
  speed: 4000,
  timeout: 120
});

const isSubmitting = ref(false);
const isCheckingHealth = ref(false);
const isLoadingFiles = ref(false);
const statusMessage = ref("Ready to execute a manual programming action.");
const responseView = ref<ManualResponse | null>(null);
const pendingPayload = ref<Record<string, unknown> | null>(null);
const activeTab = ref<LogTab>("stdout");
const streamedStdout = ref("");
const streamedStderr = ref("");
const streamConnected = ref(false);
const bitOptions = ref<SelectOption[]>([]);
const elfOptions = ref<SelectOption[]>([]);
const filteredBitOptions = ref<SelectOption[]>([]);
const filteredElfOptions = ref<SelectOption[]>([]);

let streamSocket: WebSocket | null = null;
let reconnectTimer: number | null = null;
let isPageActive = true;

const ANSI_ESCAPE_PATTERN =
  /(?:\u001B\[[0-?]*[ -/]*[@-~]|\u001B\][^\u0007]*(?:\u0007|\u001B\\)|\u001B[@-_])/g;
const BACKSPACE_PATTERN = /[^\n]\u0008/g;

const needsBit = computed(
  () => form.action === "program_bit" || form.action === "program_all"
);
const needsElf = computed(
  () => form.action === "program_elf" || form.action === "program_all"
);

const canSubmit = computed(() => {
  if (needsBit.value && !form.bit_file.trim()) return false;
  if (needsElf.value && !form.elf_file.trim()) return false;
  return true;
});

const resultTone = computed(() => {
  if (isSubmitting.value)
    return { state: "running", color: "primary", label: "Running" };
  if (!responseView.value)
    return { state: "idle", color: "grey-6", label: "Idle" };
  if (responseView.value.success)
    return { state: "success", color: "positive", label: "Success" };
  return { state: "error", color: "negative", label: "Failed" };
});

const submitLabel = computed(() =>
  isSubmitting.value ? "Executing..." : "Execute"
);

const stepBit = computed<DriverResult | null>(() => {
  if (!needsBit.value) return null;
  if (form.action === "program_bit") return responseView.value;
  return responseView.value?.data?.bit_result ?? null;
});

const stepElf = computed<DriverResult | null>(() => {
  if (!needsElf.value) return null;
  if (form.action === "program_elf") return responseView.value;
  return responseView.value?.data?.elf_result ?? null;
});

const stdoutText = computed(() => {
  if (streamedStdout.value.trim()) return streamedStdout.value.trim();

  const chunks = [
    responseView.value?.stdout,
    stepBit.value?.stdout,
    stepElf.value?.stdout
  ].filter(Boolean);
  if (!chunks.length && isSubmitting.value && !responseView.value) {
    return "Request sent to /api/manual/execute.\nWaiting for backend response.";
  }

  return chunks.join("\n\n").trim() || "No stdout captured.";
});

const stderrText = computed(() => {
  if (streamedStderr.value.trim()) return streamedStderr.value.trim();

  const chunks = [
    responseView.value?.stderr,
    stepBit.value?.stderr,
    stepElf.value?.stderr
  ].filter(Boolean);
  return chunks.join("\n\n").trim() || "No stderr captured.";
});

const jsonText = computed(() => {
  if (responseView.value)
    return JSON.stringify(
      sanitizeFilePathsForDisplay(responseView.value),
      null,
      2
    );
  if (pendingPayload.value) {
    return JSON.stringify(
      {
        status: isSubmitting.value ? "running" : "pending",
        request: sanitizeFilePathsForDisplay(pendingPayload.value)
      },
      null,
      2
    );
  }
  return "{}";
});

function sanitizedPayload() {
  return Object.fromEntries(
    Object.entries(form).filter(([, value]) => value !== "" && value !== null)
  );
}

function normalizeFileOptions(
  files: Array<{ filename: string; path: string }>
) {
  return files.map(file => ({
    label: file.filename,
    value: file.path
  }));
}

function selectedFileName(value: string | null | undefined) {
  if (!value) return "";
  const option = [...bitOptions.value, ...elfOptions.value].find(
    item => item.value === value
  );
  return option?.label ?? fileName(value);
}

function fileName(value: string) {
  return value.split(/[\\/]/).filter(Boolean).pop() ?? value;
}

function sanitizeFilePathsForDisplay(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizeFilePathsForDisplay);
  if (!value || typeof value !== "object") return value;

  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, item]) => {
      if (
        typeof item === "string" &&
        ["bit_file", "elf_file", "bit_path", "elf_path"].includes(key)
      ) {
        return [key, fileName(item)];
      }
      return [key, sanitizeFilePathsForDisplay(item)];
    })
  );
}

function filterBitOptions(
  value: string,
  update: (callback: () => void) => void
) {
  update(() => {
    const needle = value.toLowerCase();
    filteredBitOptions.value = bitOptions.value.filter(
      option =>
        option.label.toLowerCase().includes(needle) ||
        option.value.toLowerCase().includes(needle)
    );
  });
}

function filterElfOptions(
  value: string,
  update: (callback: () => void) => void
) {
  update(() => {
    const needle = value.toLowerCase();
    filteredElfOptions.value = elfOptions.value.filter(
      option =>
        option.label.toLowerCase().includes(needle) ||
        option.value.toLowerCase().includes(needle)
    );
  });
}

async function loadFileOptions() {
  isLoadingFiles.value = true;
  try {
    const response = await fetch("/api/uploads");
    const data = (await response.json()) as {
      bit?: Array<{ filename: string; path: string }>;
      elf?: Array<{ filename: string; path: string }>;
    };

    bitOptions.value = normalizeFileOptions(data.bit ?? []);
    elfOptions.value = normalizeFileOptions(data.elf ?? []);
    filteredBitOptions.value = bitOptions.value;
    filteredElfOptions.value = elfOptions.value;

    const firstBitOption = bitOptions.value[0];
    if (
      firstBitOption &&
      !bitOptions.value.some(option => option.value === form.bit_file)
    ) {
      form.bit_file = firstBitOption.value;
    }

    const firstElfOption = elfOptions.value[0];
    if (
      firstElfOption &&
      !elfOptions.value.some(option => option.value === form.elf_file)
    ) {
      form.elf_file = firstElfOption.value;
    }
  } catch (error) {
    statusMessage.value =
      error instanceof Error ? error.message : "Unable to load file list.";
  } finally {
    isLoadingFiles.value = false;
  }
}

function websocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/ws/terminal`;
}

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function appendStreamChunk(target: "stdout" | "stderr", chunk: string) {
  if (!chunk.trim()) return;

  if (target === "stderr") {
    streamedStderr.value = `${streamedStderr.value}${chunk}`;
    if (isSubmitting.value) activeTab.value = "stderr";
    return;
  }

  streamedStdout.value = `${streamedStdout.value}${chunk}`;
}

function sanitizeTerminalChunk(chunk: string) {
  let normalized = chunk.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  normalized = normalized.replace(ANSI_ESCAPE_PATTERN, "");

  while (BACKSPACE_PATTERN.test(normalized)) {
    normalized = normalized.replace(BACKSPACE_PATTERN, "");
  }

  return normalized.replace(/\u0000/g, "");
}

function handleStreamMessage(rawMessage: string) {
  if (!rawMessage) return;
  if (rawMessage.startsWith("Connected to backend shell:")) return;

  const normalized = sanitizeTerminalChunk(rawMessage);
  if (normalized.includes("success=") && normalized.includes("message:"))
    return;

  for (const line of normalized.split("\n")) {
    if (!line.trim()) continue;
    if (line.startsWith("[stderr] ")) {
      appendStreamChunk("stderr", `${line.slice(9)}\n`);
      continue;
    }
    appendStreamChunk("stdout", `${line}\n`);
  }
}

function scheduleReconnect() {
  if (!isPageActive || reconnectTimer !== null) return;
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connectStreamSocket();
  }, 1500);
}

function connectStreamSocket() {
  if (
    streamSocket &&
    (streamSocket.readyState === WebSocket.OPEN ||
      streamSocket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  streamSocket = new WebSocket(websocketUrl());

  streamSocket.onopen = () => {
    streamConnected.value = true;
    clearReconnectTimer();
  };

  streamSocket.onmessage = event => {
    handleStreamMessage(String(event.data));
  };

  streamSocket.onerror = () => {
    streamConnected.value = false;
  };

  streamSocket.onclose = () => {
    streamConnected.value = false;
    streamSocket = null;
    scheduleReconnect();
  };
}

function disconnectStreamSocket() {
  clearReconnectTimer();
  streamConnected.value = false;
  if (streamSocket) {
    streamSocket.close();
    streamSocket = null;
  }
}

async function checkHealth() {
  isCheckingHealth.value = true;
  try {
    const response = await fetch("/api/health");
    const data = (await response.json()) as { status?: string };
    statusMessage.value = response.ok
      ? `Backend is ${data.status ?? "ok"}.`
      : "Backend health check failed.";
  } catch (error) {
    statusMessage.value =
      error instanceof Error ? error.message : "Unable to reach backend.";
  } finally {
    isCheckingHealth.value = false;
  }
}

async function submitManualAction() {
  isSubmitting.value = true;
  statusMessage.value = "Executing manual programming action...";
  responseView.value = null;
  pendingPayload.value = sanitizedPayload();
  streamedStdout.value = "";
  streamedStderr.value = "";
  activeTab.value = "stdout";

  try {
    const response = await fetch("/api/manual/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pendingPayload.value)
    });
    const responseText = await response.text();
    let data: ManualResponse | null = null;
    try {
      data = JSON.parse(responseText || "{}") as ManualResponse;
    } catch (error) {
      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}: ${responseText || response.statusText}`
        );
      }
      throw error;
    }
    if (!response.ok) {
      throw new Error(
        data?.message || responseText || `HTTP ${response.status}`
      );
    }
    if (!data) throw new Error("Backend returned an empty response.");
    responseView.value = data;
    statusMessage.value =
      data.message ||
      (data.success ? "Execution completed." : "Execution failed.");
    activeTab.value = data.success ? "stdout" : data.stderr ? "stderr" : "json";
  } catch (error) {
    responseView.value = {
      success: false,
      message: "Network request failed",
      data: null,
      stdout: "",
      stderr: error instanceof Error ? error.message : "Unknown request error",
      returncode: null
    };
    statusMessage.value =
      "Manual programming request failed before reaching backend.";
    activeTab.value = "stderr";
  } finally {
    isSubmitting.value = false;
  }
}

async function copyPayload() {
  await copyToClipboard(JSON.stringify(sanitizedPayload(), null, 2));
  $q.notify({ type: "positive", message: "Payload copied." });
}

function clearResult() {
  responseView.value = null;
  pendingPayload.value = null;
  streamedStdout.value = "";
  streamedStderr.value = "";
  statusMessage.value = "Result cleared.";
  activeTab.value = "stdout";
}

function stepIcon(result: DriverResult | null) {
  if (!result) return "more_horiz";
  return result.success ? "check_circle" : "cancel";
}

function stepColor(result: DriverResult | null) {
  if (!result) return "grey-5";
  return result.success ? "positive" : "negative";
}

function stepMessage(result: DriverResult | null, enabled: boolean) {
  if (!enabled) return "Not included in this action.";
  if (!result) return "Waiting for execution.";
  return result.message || (result.success ? "Completed." : "Failed.");
}

onMounted(() => {
  connectStreamSocket();
  loadFileOptions();
});

onBeforeUnmount(() => {
  isPageActive = false;
  disconnectStreamSocket();
});
</script>
