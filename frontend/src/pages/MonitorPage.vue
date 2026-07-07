<template>
  <q-page class="page">
    <section class="page-section">
      <div class="section-head">
        <div class="section-kicker">Monitor</div>
        <h1 class="section-title">Serial Monitor</h1>
      </div>

      <div class="serial-monitor-grid">
        <section class="surface-block serial-control">
          <div class="block-head">
            <h2 class="block-title">UART</h2>
            <div class="block-head__badges">
              <q-badge
                rounded
                :color="socketConnected ? 'positive' : 'grey-6'"
                text-color="white"
                :label="socketConnected ? 'WebSocket On' : 'WebSocket Off'"
              />
              <q-badge
                rounded
                :color="uartConnected ? 'positive' : 'grey-6'"
                text-color="white"
                :label="uartConnected ? 'UART Open' : 'UART Closed'"
              />
            </div>
          </div>

          <div class="form-grid">
            <q-select
              v-model="form.port"
              outlined
              dense
              emit-value
              map-options
              label="Port"
              :loading="isLoadingPorts"
              :options="portOptions"
            />

            <q-select
              v-model.number="form.baudrate"
              outlined
              dense
              emit-value
              map-options
              label="Baudrate"
              :options="baudrateOptions"
            />

            <div class="serial-baudrate-editor">
              <q-input
                v-model.number="customBaudrate"
                outlined
                dense
                type="number"
                label="Custom Baudrate"
                min="1"
              />
              <q-btn
                color="secondary"
                text-color="white"
                unelevated
                no-caps
                icon="bookmark_add"
                :disable="!canSaveCustomBaudrate"
                label="Save"
                @click="saveCustomBaudrate"
              />
            </div>

            <q-select
              v-model="form.receiveFormat"
              outlined
              dense
              emit-value
              map-options
              label="Receive"
              :options="formatOptions"
            />

            <q-select
              v-model="form.sendFormat"
              outlined
              dense
              emit-value
              map-options
              label="Send"
              :options="formatOptions"
            />
          </div>

          <div class="button-row">
            <q-btn
              color="primary"
              text-color="white"
              unelevated
              no-caps
              :icon="uartConnected ? 'link_off' : 'settings_input_component'"
              :disable="!canToggleConnection"
              :loading="isTogglingConnection"
              :label="uartConnected ? 'Close UART' : 'Open UART'"
              @click="toggleUart"
            >
              <q-tooltip>{{
                uartConnected
                  ? "Close current UART connection"
                  : "Open selected UART port"
              }}</q-tooltip>
            </q-btn>
            <q-btn
              flat
              round
              icon="refresh"
              color="grey-8"
              :loading="isLoadingPorts"
              @click="loadPorts"
            >
              <q-tooltip>Refresh ports</q-tooltip>
            </q-btn>
          </div>

          <div class="status-line" :class="`status-line--${statusTone}`">
            {{ statusMessage }}
          </div>

          <q-input
            v-model="sendText"
            class="serial-send-input"
            outlined
            autogrow
            type="textarea"
            label="Payload"
          />

          <div class="serial-send-actions">
            <q-toggle v-model="appendNewline" dense label="Newline" />
            <div class="serial-send-actions__buttons">
              <q-btn
                color="primary"
                text-color="white"
                unelevated
                no-caps
                icon="send"
                :disable="!canSend"
                label="Send"
                @click="sendUart"
              />
              <q-btn
                flat
                round
                icon="backspace"
                color="grey-8"
                @click="sendText = ''"
              >
                <q-tooltip>Clear payload</q-tooltip>
              </q-btn>
            </div>
          </div>
        </section>

        <section class="surface-block serial-output">
          <div class="block-head">
            <h2 class="block-title">Data</h2>
            <div class="serial-output-actions">
              <q-badge
                rounded
                color="grey-7"
                text-color="white"
                :label="`${receivedBytes} B`"
              />
              <q-btn
                flat
                round
                :icon="autoScroll ? 'vertical_align_bottom' : 'pause'"
                color="grey-8"
                @click="autoScroll = !autoScroll"
              >
                <q-tooltip>{{
                  autoScroll ? "Auto scroll on" : "Auto scroll off"
                }}</q-tooltip>
              </q-btn>
              <q-btn
                flat
                round
                icon="delete_sweep"
                color="grey-8"
                @click="clearLog"
              >
                <q-tooltip>Clear data</q-tooltip>
              </q-btn>
            </div>
          </div>

          <pre ref="logElement" class="serial-console">{{ displayLog }}</pre>
        </section>
      </div>
    </section>
  </q-page>
</template>

<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref
} from "vue";

type SerialFormat = "text" | "hex";

type SerialPortItem = {
  device: string;
  description?: string | null;
};

type PortResponse = {
  items: SerialPortItem[];
};

type UartMessage = {
  type?: string;
  action?: string;
  state?: string;
  success?: boolean;
  message?: string;
  hex?: string;
  text?: string;
  size?: number;
  data?: {
    payload?: {
      hex?: string;
      text?: string;
      size?: number;
    };
  };
};

const MAX_LOG_CHARS = 220000;
const FLUSH_INTERVAL_MS = 80;
const CUSTOM_BAUDRATES_STORAGE_KEY = "serial-monitor-custom-baudrates";
const DEFAULT_BAUDRATES = [
  9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600
];

const form = reactive({
  port: "",
  baudrate: 115200,
  receiveFormat: "text" as SerialFormat,
  sendFormat: "text" as SerialFormat
});

const customBaudrates = ref<number[]>([]);
const customBaudrate = ref<number | null>(null);

const baudrateOptions = computed(() =>
  [...new Set([...DEFAULT_BAUDRATES, ...customBaudrates.value])]
    .sort((left, right) => left - right)
    .map(value => ({
      label: String(value),
      value
    }))
);

const formatOptions = [
  { label: "Text", value: "text" },
  { label: "HEX", value: "hex" }
];

const ports = ref<SerialPortItem[]>([]);
const isLoadingPorts = ref(false);
const isOpening = ref(false);
const isClosing = ref(false);
const socketConnected = ref(false);
const uartConnected = ref(false);
const statusMessage = ref("Ready.");
const statusTone = ref<"idle" | "success" | "error">("idle");
const sendText = ref("");
const appendNewline = ref(false);
const displayLog = ref("");
const receivedBytes = ref(0);
const autoScroll = ref(true);
const logElement = ref<HTMLElement | null>(null);
const isPageActive = ref(true);

let socket: WebSocket | null = null;
let flushTimer: number | null = null;
let reconnectTimer: number | null = null;
const pendingChunks: string[] = [];

const portOptions = computed(() =>
  ports.value.map(port => ({
    label: port.description
      ? `${port.device} - ${port.description}`
      : port.device,
    value: port.device
  }))
);

const isTogglingConnection = computed(() => isOpening.value || isClosing.value);
const canToggleConnection = computed(() => {
  if (!socketConnected.value || isTogglingConnection.value) return false;
  if (uartConnected.value) return true;
  return Boolean(form.port);
});
const canSaveCustomBaudrate = computed(() => {
  if (!customBaudrate.value || customBaudrate.value <= 0) return false;
  return !baudrateOptions.value.some(
    option => option.value === customBaudrate.value
  );
});
const canSend = computed(
  () =>
    uartConnected.value && socketConnected.value && sendText.value.length > 0
);

function loadCustomBaudrates() {
  const saved = window.localStorage.getItem(CUSTOM_BAUDRATES_STORAGE_KEY);
  if (!saved) return;

  try {
    const parsed = JSON.parse(saved) as unknown;
    if (!Array.isArray(parsed)) return;

    customBaudrates.value = parsed
      .map(value => Number(value))
      .filter(value => Number.isInteger(value) && value > 0);
  } catch {
    customBaudrates.value = [];
  }
}

function persistCustomBaudrates() {
  window.localStorage.setItem(
    CUSTOM_BAUDRATES_STORAGE_KEY,
    JSON.stringify(customBaudrates.value)
  );
}

function websocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/ws/uart`;
}

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function scheduleReconnect() {
  if (!isPageActive.value || reconnectTimer !== null) return;
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connectSocket();
  }, 1500);
}

function sendSocket(payload: Record<string, unknown>) {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    setStatus("WebSocket is not connected.", "error");
    return false;
  }
  socket.send(JSON.stringify(payload));
  return true;
}

function connectSocket() {
  if (
    socket &&
    (socket.readyState === WebSocket.OPEN ||
      socket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  socket = new WebSocket(websocketUrl());

  socket.onopen = () => {
    socketConnected.value = true;
    clearReconnectTimer();
    setStatus("WebSocket connected.", "success");
  };

  socket.onmessage = event => {
    handleSocketMessage(JSON.parse(String(event.data)) as UartMessage);
  };

  socket.onerror = () => {
    socketConnected.value = false;
    setStatus("WebSocket error.", "error");
  };

  socket.onclose = () => {
    isOpening.value = false;
    isClosing.value = false;
    socketConnected.value = false;
    uartConnected.value = false;
    socket = null;
    setStatus("WebSocket closed.", "idle");
    scheduleReconnect();
  };
}

function handleSocketMessage(message: UartMessage) {
  if (message.type === "status") {
    setStatus(
      message.state === "ready"
        ? "UART monitor ready."
        : `State: ${message.state ?? "unknown"}.`,
      "idle"
    );
    return;
  }

  if (message.type === "result") {
    if (message.action === "open") {
      isOpening.value = false;
      uartConnected.value = Boolean(message.success);
    }
    if (message.action === "close") {
      isClosing.value = false;
      uartConnected.value = false;
    }
    if (message.action === "write" && message.success) {
      const outgoing = formatOutgoingData(message);
      if (outgoing) {
        pendingChunks.push(outgoing);
      }
    }
    setStatus(
      message.message || `${message.action ?? "Action"} completed.`,
      message.success ? "success" : "error"
    );
    return;
  }

  if (message.type === "error") {
    isOpening.value = false;
    isClosing.value = false;
    setStatus(message.message || "UART error.", "error");
    return;
  }

  if (message.type === "data") {
    receivedBytes.value += message.size ?? 0;
    pendingChunks.push(formatIncomingData(message));
  }
}

function formatIncomingData(message: UartMessage) {
  if (form.receiveFormat === "hex") {
    return `${message.hex ?? ""}\n`;
  }
  return message.text ?? "";
}

function formatOutgoingData(message: UartMessage) {
  const payload = message.data?.payload;
  if (!payload) return "";
  if (form.receiveFormat === "hex") {
    return `[TX] ${payload.hex ?? ""}\n`;
  }
  return `[TX] ${payload.text ?? ""}\n`;
}

function setStatus(message: string, tone: "idle" | "success" | "error") {
  statusMessage.value = message;
  statusTone.value = tone;
}

function flushLog() {
  if (!pendingChunks.length) return;

  const nextLog = `${displayLog.value}${pendingChunks.join("")}`;
  pendingChunks.length = 0;
  displayLog.value =
    nextLog.length > MAX_LOG_CHARS ? nextLog.slice(-MAX_LOG_CHARS) : nextLog;

  if (autoScroll.value) {
    void nextTick(() => {
      if (logElement.value) {
        logElement.value.scrollTop = logElement.value.scrollHeight;
      }
    });
  }
}

async function loadPorts() {
  isLoadingPorts.value = true;
  try {
    const response = await fetch("/api/serial-ports");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = (await response.json()) as PortResponse;
    ports.value = data.items ?? [];
    if (!form.port && ports.value[0]) {
      form.port = ports.value[0].device;
    }
  } catch (error) {
    setStatus(
      error instanceof Error ? error.message : "Failed to load ports.",
      "error"
    );
  } finally {
    isLoadingPorts.value = false;
  }
}

function openUart() {
  isOpening.value = true;
  setStatus("Opening UART...", "idle");
  const sent = sendSocket({
    type: "open",
    port: form.port,
    baudrate: form.baudrate
  });
  if (!sent) {
    isOpening.value = false;
  }
}

function closeUart() {
  isClosing.value = true;
  setStatus("Closing UART...", "idle");
  const sent = sendSocket({ type: "close" });
  if (!sent) {
    isClosing.value = false;
  }
}

function toggleUart() {
  if (uartConnected.value) {
    closeUart();
    return;
  }
  openUart();
}

function sendUart() {
  sendSocket({
    type: "write",
    data: sendText.value,
    format: form.sendFormat,
    append_newline: appendNewline.value
  });
}

function clearLog() {
  pendingChunks.length = 0;
  displayLog.value = "";
  receivedBytes.value = 0;
}

function saveCustomBaudrate() {
  if (!customBaudrate.value || customBaudrate.value <= 0) return;

  customBaudrates.value = [...customBaudrates.value, customBaudrate.value].sort(
    (left, right) => left - right
  );
  persistCustomBaudrates();
  form.baudrate = customBaudrate.value;
  customBaudrate.value = null;
  setStatus("Custom baudrate saved.", "success");
}

onMounted(() => {
  loadCustomBaudrates();
  connectSocket();
  void loadPorts();
  flushTimer = window.setInterval(flushLog, FLUSH_INTERVAL_MS);
});

onBeforeUnmount(() => {
  isPageActive.value = false;
  clearReconnectTimer();
  if (flushTimer !== null) {
    window.clearInterval(flushTimer);
    flushTimer = null;
  }
  if (socket) {
    socket.close();
    socket = null;
  }
});
</script>
