<template>
  <q-page class="scope-console-page">
    <section class="scope-console">
      <header class="scope-topbar">
        <div class="scope-topbar__brand">
          <div class="scope-title">示波器调试</div>
          <q-badge
            rounded
            :color="mode === 'mock' ? 'blue-grey-7' : 'primary'"
            text-color="white"
            :label="mode === 'mock' ? 'Mock Mode' : 'API Mode'"
          />
          <q-badge
            rounded
            :color="statusColor"
            text-color="white"
            :label="connectionStatus"
          />
        </div>

        <div class="scope-topbar__identity">
          <span>Scope IP: {{ connection.ip }}</span>
          <span>Port: {{ connection.port }}</span>
          <span class="scope-idn">
            IDN: {{ idn || "--" }}
            <q-tooltip v-if="idn">{{ idn }}</q-tooltip>
          </span>
        </div>

        <div class="scope-topbar__actions">
          <q-btn flat dense no-caps icon="settings" label="连接设置" @click="showConnectionDialog = true" />
          <q-btn
            unelevated
            dense
            no-caps
            color="primary"
            icon="cable"
            label="检测连接"
            :loading="activeAction === 'detect'"
            :disable="isBusy"
            @click="handleDetect"
          />
          <q-btn flat dense no-caps icon="history" label="历史记录" @click="showHistoryDialog = true" />
          <q-btn flat dense no-caps icon="data_object" label="原始数据" @click="showRawDialog = true" />
          <q-btn flat dense round color="grey-8" icon="delete_sweep" @click="clearScopeState">
            <q-tooltip>清空结果</q-tooltip>
          </q-btn>
        </div>
      </header>

      <main class="scope-workbench">
        <section class="scope-screen-card">
          <div class="scope-screen" :class="{ 'scope-screen--loading': activeAction === 'waveform' }">
            <div class="scope-screen__corner scope-screen__corner--left">
              <strong>{{ channel }}</strong>
              <span>{{ coupling }} / {{ scale }} V/div / {{ offset }} V</span>
            </div>
            <div class="scope-screen__corner scope-screen__corner--right">
              <strong>Trigger: Auto</strong>
              <span>Sample: {{ waveformSampleCount }}</span>
            </div>
            <q-badge
              v-if="waveformError"
              class="scope-screen__error"
              color="negative"
              text-color="white"
              :label="waveformError"
            />

            <svg class="scope-wave-svg" viewBox="0 0 960 480" preserveAspectRatio="none">
              <line class="scope-axis" x1="0" y1="240" x2="960" y2="240" />
              <line class="scope-axis" x1="480" y1="0" x2="480" y2="480" />
              <line class="scope-trigger" x1="620" y1="0" x2="620" y2="480" />
              <polyline v-if="waveformPolyline" class="scope-wave-line" :points="waveformPolyline" />
            </svg>

            <div v-if="!waveformPolyline" class="scope-screen__empty">
              {{ mode === "mock" ? "Mock waveform ready" : "点击读取波形获取 preview" }}
            </div>
            <q-inner-loading :showing="activeAction === 'waveform'" color="primary" label="读取波形中..." />
          </div>
          <footer class="scope-screen-footer">
            <span>{{ waveformFooter }}</span>
            <div class="scope-screen-footer__actions">
              <q-btn flat dense no-caps icon="settings" label="波形设置" @click="showWaveformDialog = true" />
              <q-btn
                unelevated
                dense
                no-caps
                color="primary"
                icon="timeline"
                label="读取波形"
                :loading="activeAction === 'waveform'"
                :disable="isBusy"
                @click="handleReadWaveform"
              />
            </div>
          </footer>
        </section>

        <aside class="scope-control-rack">
          <section class="scope-control-group">
            <div class="scope-control-title">Channel</div>
            <q-btn-toggle
              v-model="channel"
              spread
              unelevated
              toggle-color="primary"
              :options="channelOptions"
            />
            <q-btn-toggle
              v-model="coupling"
              spread
              unelevated
              toggle-color="blue-grey-8"
              :options="couplingOptions"
            />
          </section>

          <section class="scope-control-group">
            <div class="scope-control-title">Vertical</div>
            <div class="scope-stepper">
              <span>Scale</span>
              <q-btn dense round flat icon="remove" @click="nudgeScale(-0.1)" />
              <button class="scope-value-button" @click="openExactInput('scale')">{{ scale }} V/div</button>
              <q-btn dense round flat icon="add" @click="nudgeScale(0.1)" />
            </div>
            <div class="scope-stepper">
              <span>Offset</span>
              <q-btn dense round flat icon="remove" @click="nudgeOffset(-0.1)" />
              <button class="scope-value-button" @click="openExactInput('offset')">{{ offset }} V</button>
              <q-btn dense round flat icon="add" @click="nudgeOffset(0.1)" />
            </div>
          </section>

          <section class="scope-control-group">
            <div class="scope-control-title">Measure</div>
            <q-select
              v-model="measure"
              outlined
              dense
              emit-value
              map-options
              label="Measure Type"
              :options="measureOptions"
            />
            <div class="scope-panel-actions">
              <q-btn
                unelevated
                no-caps
                color="primary"
                icon="speed"
                label="单次测量"
                :loading="activeAction === 'measure'"
                :disable="isBusy"
                @click="handleMeasure"
              />
              <q-btn
                outline
                no-caps
                color="primary"
                icon="rule"
                label="范围设置"
                @click="showRangeDialog = true"
              />
              <q-btn
                outline
                no-caps
                color="secondary"
                icon="tune"
                label="应用通道"
                :loading="activeAction === 'channel'"
                :disable="isBusy"
                @click="handleApplyChannel"
              />
              <q-btn
                outline
                no-caps
                color="primary"
                icon="data_object"
                label="生成 TestStep JSON"
                @click="generateTestStep"
              />
            </div>
          </section>

          <section class="scope-control-group">
            <div class="scope-control-title">Auto</div>
            <q-btn outline disable no-caps icon="auto_fix_high" label="Auto Scale" />
            <q-btn-toggle
              v-model="runState"
              spread
              unelevated
              toggle-color="positive"
              :options="runOptions"
            />
          </section>
        </aside>
      </main>

      <footer class="scope-measure-bar">
        <button
          v-for="item in measurementCards"
          :key="item.measure"
          class="scope-measure-tile"
          @click="openRangeFor(item.measure)"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <q-badge rounded :color="statusBadgeColor(item.status)" text-color="white" :label="item.status" />
        </button>
      </footer>
    </section>

    <q-dialog v-model="showConnectionDialog">
      <q-card class="scope-dialog-card">
        <q-card-section>
          <div class="dialog-title">连接设置</div>
          <div class="dialog-grid">
            <q-btn-toggle
              v-model="mode"
              spread
              unelevated
              toggle-color="primary"
              :options="modeOptions"
            />
            <q-input v-model="connection.ip" outlined dense label="Scope IP" />
            <q-input v-model.number="connection.port" outlined dense type="number" label="Port" />
            <q-input v-model.number="connection.timeout_ms" outlined dense type="number" label="Timeout(ms)" />
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat no-caps label="取消" v-close-popup />
          <q-btn outline no-caps color="primary" label="检测连接" :loading="activeAction === 'detect'" @click="handleDetect" />
          <q-btn unelevated no-caps color="primary" label="保存" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showRangeDialog">
      <q-card class="scope-dialog-card">
        <q-card-section>
          <div class="dialog-title">测量范围设置</div>
          <div class="dialog-grid">
            <q-select
              v-model="rangeForm.measure"
              outlined
              dense
              emit-value
              map-options
              label="Measure Type"
              :options="measureOptions"
            />
            <q-input v-model.number="rangeForm.min" outlined dense clearable type="number" label="Min" />
            <q-input v-model.number="rangeForm.max" outlined dense clearable type="number" label="Max" />
            <q-input :model-value="unitFor(rangeForm.measure)" outlined dense readonly label="Unit" />
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat no-caps label="清除范围" @click="clearRange" />
          <q-btn unelevated no-caps color="primary" label="保存" @click="saveRange" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showWaveformDialog">
      <q-card class="scope-dialog-card">
        <q-card-section>
          <div class="dialog-title">波形读取设置</div>
          <div class="dialog-grid">
            <q-input
              v-model.number="waveformConfig.points"
              outlined
              dense
              type="number"
              label="Points"
              hint="API Mode 下请求后端读取点数"
            />
            <q-input
              v-model.number="waveformConfig.preview_points"
              outlined
              dense
              type="number"
              label="Preview Points"
              hint="前端绘制的预览点数"
            />
          </div>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat no-caps label="取消" v-close-popup />
          <q-btn unelevated no-caps color="primary" label="保存" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showRawDialog">
      <q-card class="scope-raw-dialog">
        <q-card-section class="dialog-head">
          <div class="dialog-title">原始数据</div>
          <q-btn flat round icon="content_copy" @click="copyRawJson">
            <q-tooltip>复制 JSON</q-tooltip>
          </q-btn>
        </q-card-section>
        <q-card-section>
          <pre class="scope-json-view">{{ rawJsonText }}</pre>
        </q-card-section>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showHistoryDialog">
      <q-card class="scope-history-dialog">
        <q-card-section class="dialog-head">
          <div class="dialog-title">历史记录</div>
          <q-badge rounded color="grey-7" text-color="white" :label="`${history.length} / 20`" />
        </q-card-section>
        <q-card-section>
          <q-table
            flat
            dense
            row-key="id"
            :rows="history"
            :columns="historyColumns"
            :rows-per-page-options="[20]"
          />
        </q-card-section>
      </q-card>
    </q-dialog>

    <q-dialog v-model="showExactDialog">
      <q-card class="scope-exact-dialog">
        <q-card-section>
          <div class="dialog-title">{{ exactTarget === "scale" ? "Scale V/div" : "Offset V" }}</div>
          <q-input v-model.number="exactValue" outlined autofocus type="number" label="Value" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat no-caps label="取消" v-close-popup />
          <q-btn unelevated no-caps color="primary" label="应用" @click="applyExactValue" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { copyToClipboard, useQuasar } from "quasar";
import {
  detectScope,
  measureScope,
  readScopeWaveform,
  setScopeChannel,
  type ScopeDriverResult,
  type ScopeMode,
  type ScopeWaveformData,
  type ScopeWaveformSample
} from "@/services/scopeApi";

type ConnectionStatus = "idle" | "connected" | "error" | "measuring";
type MeasureType = "vpp" | "vmax" | "vmin" | "vrms" | "vavg" | "freq" | "period" | "duty";
type ActiveAction = "detect" | "channel" | "measure" | "waveform" | null;

type MeasurementRecord = {
  value: number;
  unit: string;
  status: "PASS" | "FAIL" | "UNKNOWN";
  message?: string;
};

type HistoryRow = {
  id: number;
  time: string;
  action: string;
  channel: string;
  measure: string;
  value: string;
  unit: string;
  status: string;
  message: string;
};

const $q = useQuasar();
const mode = ref<ScopeMode>("mock");
const connectionStatus = ref<ConnectionStatus>("idle");
const activeAction = ref<ActiveAction>(null);
const idn = ref("");
const channel = ref("CH1");
const coupling = ref("DC");
const scale = ref(0.5);
const offset = ref(0);
const measure = ref<MeasureType>("vpp");
const runState = ref<"run" | "stop">("run");
const rawResponse = ref<ScopeDriverResult | null>(null);
const waveformResponse = ref<ScopeDriverResult<ScopeWaveformData> | null>(null);
const generatedTestStepJson = ref<Record<string, unknown> | null>(null);
const waveformSamples = ref<ScopeWaveformSample[]>([]);
const waveformError = ref("");
const latestMeasurements = reactive<Partial<Record<MeasureType, MeasurementRecord>>>({});
const measureRanges = reactive<Partial<Record<MeasureType, { min?: number; max?: number }>>>({});
const history = ref<HistoryRow[]>([]);

const showConnectionDialog = ref(false);
const showRangeDialog = ref(false);
const showWaveformDialog = ref(false);
const showRawDialog = ref(false);
const showHistoryDialog = ref(false);
const showExactDialog = ref(false);
const exactTarget = ref<"scale" | "offset">("scale");
const exactValue = ref(0);

const connection = reactive({
  ip: "192.168.31.28",
  port: 5025,
  timeout_ms: 5000
});

const waveformConfig = reactive({
  points: 12000,
  preview_points: 300
});

const rangeForm = reactive<{
  measure: MeasureType;
  min: number | null;
  max: number | null;
}>({
  measure: "vpp",
  min: null,
  max: null
});

const modeOptions = [
  { label: "Mock Mode", value: "mock" },
  { label: "API Mode", value: "api" }
];

const channelOptions = ["CH1", "CH2", "CH3", "CH4"].map(value => ({ label: value, value }));
const couplingOptions = ["DC", "AC", "GND"].map(value => ({ label: value, value }));
const runOptions = [
  { label: "Run", value: "run" },
  { label: "Stop", value: "stop" }
];
const measureOptions = [
  { label: "vpp", value: "vpp" },
  { label: "vmax", value: "vmax" },
  { label: "vmin", value: "vmin" },
  { label: "vrms", value: "vrms" },
  { label: "vavg", value: "vavg" },
  { label: "freq", value: "freq" },
  { label: "period", value: "period" },
  { label: "duty", value: "duty" }
];

const measurementOrder: { label: string; measure: MeasureType }[] = [
  { label: "VPP", measure: "vpp" },
  { label: "FREQ", measure: "freq" },
  { label: "VRMS", measure: "vrms" },
  { label: "DUTY", measure: "duty" },
  { label: "PERIOD", measure: "period" }
];

const historyColumns = [
  { name: "time", label: "time", field: "time", align: "left" as const },
  { name: "action", label: "action", field: "action", align: "left" as const },
  { name: "channel", label: "channel", field: "channel", align: "left" as const },
  { name: "measure", label: "measure", field: "measure", align: "left" as const },
  { name: "value", label: "value", field: "value", align: "right" as const },
  { name: "unit", label: "unit", field: "unit", align: "left" as const },
  { name: "status", label: "status", field: "status", align: "left" as const },
  { name: "message", label: "message", field: "message", align: "left" as const }
];

const isBusy = computed(() => activeAction.value !== null);
const statusColor = computed(() => {
  if (connectionStatus.value === "connected") return "positive";
  if (connectionStatus.value === "measuring") return "orange";
  if (connectionStatus.value === "error") return "negative";
  return "grey-7";
});

const displaySamples = computed(() => {
  if (waveformSamples.value.length) return waveformSamples.value;
  if (mode.value === "mock") return createMockSamples(300);
  return [];
});

const waveformPolyline = computed(() => samplesToPolyline(displaySamples.value));
const waveformSampleCount = computed(() => {
  const data = waveformResponse.value?.data;
  return data?.preview_points || displaySamples.value.length || "--";
});
const waveformFooter = computed(() => {
  const data = waveformResponse.value?.data;
  if (data?.points) return `Preview only · ${data.preview_points || displaySamples.value.length} of ${data.points} points`;
  return mode.value === "mock" ? "Preview only · mock signal" : "Preview only";
});

const measurementCards = computed(() =>
  measurementOrder.map(item => {
    const record = latestMeasurements[item.measure];
    return {
      ...item,
      value: record ? `${formatNumber(record.value)} ${record.unit}` : "--",
      status: record?.status ?? "UNKNOWN"
    };
  })
);

const rawJsonText = computed(() =>
  JSON.stringify(
    {
      rawResponse: rawResponse.value,
      waveform: waveformResponse.value,
      test_step: generatedTestStepJson.value
    },
    null,
    2
  )
);

async function handleDetect() {
  activeAction.value = "detect";
  connectionStatus.value = "measuring";
  try {
    const result =
      mode.value === "mock"
        ? mockDetect()
        : await detectScope({ ...connection });
    rawResponse.value = result;
    assertResult(result);
    idn.value = String((result.data as { idn?: string })?.idn || result.stdout || "MOCK,SCOPE,FPGA-DEBUG,1.0");
    connectionStatus.value = "connected";
    pushHistory("scope_idn", result);
    notify("positive", "示波器连接成功。");
  } catch (error) {
    connectionStatus.value = "error";
    handleError(error, "scope_idn", "示波器连接失败。");
  } finally {
    activeAction.value = null;
  }
}

async function handleApplyChannel() {
  activeAction.value = "channel";
  try {
    const payload = {
      ...connection,
      channel: channel.value,
      enabled: true,
      scale: scale.value,
      offset: offset.value,
      coupling: coupling.value
    };
    const result = mode.value === "mock" ? mockOk("mock channel configured", payload) : await setScopeChannel(payload);
    rawResponse.value = result;
    assertResult(result);
    pushHistory("scope_set_channel", result);
    notify("positive", "通道配置已应用。");
  } catch (error) {
    connectionStatus.value = "error";
    handleError(error, "scope_set_channel", "通道配置失败。");
  } finally {
    activeAction.value = null;
  }
}

async function handleMeasure() {
  activeAction.value = "measure";
  connectionStatus.value = connectionStatus.value === "idle" ? "measuring" : connectionStatus.value;
  try {
    const payload = {
      ...connection,
      channel: channel.value,
      measure: measure.value,
      ...(measureRanges[measure.value]
        ? { expected: measureRanges[measure.value] }
        : {})
    };
    const result = mode.value === "mock" ? mockMeasure(measure.value) : await measureScope(payload);
    rawResponse.value = result;
    assertResult(result);
    applyMeasurementResult(measure.value, result);
    pushHistory("scope_measure", result);
    notify("positive", "单次测量完成。");
  } catch (error) {
    connectionStatus.value = "error";
    handleError(error, "scope_measure", "单次测量失败。");
  } finally {
    activeAction.value = null;
  }
}

async function handleReadWaveform() {
  activeAction.value = "waveform";
  waveformError.value = "";
  try {
    const payload = {
      ...connection,
      channel: channel.value,
      points: waveformConfig.points,
      preview_points: waveformConfig.preview_points,
      waveform_format: "BYTE",
      binary: true,
      datatype: "B"
    };
    const result = mode.value === "mock" ? mockWaveform() : await readScopeWaveform(payload);
    waveformResponse.value = result;
    rawResponse.value = result;
    assertResult(result);
    waveformSamples.value = normalizeWaveformSamples(result.data);
    pushHistory("scope_waveform", result);
    notify("positive", "波形读取完成。");
  } catch (error) {
    waveformError.value = error instanceof Error ? error.message : "波形读取失败";
    handleError(error, "scope_waveform", "波形读取失败。");
  } finally {
    activeAction.value = null;
  }
}

function generateTestStep() {
  const expected: Record<string, unknown> = { unit: unitFor(measure.value) };
  const range = measureRanges[measure.value];
  if (range?.min !== undefined) expected.min = range.min;
  if (range?.max !== undefined) expected.max = range.max;
  generatedTestStepJson.value = {
    step_type: "scope_measure",
    name: `测量 ${channel.value} ${measure.value}`,
    config_json: {
      channel: channel.value,
      measure: measure.value
    },
    expected_json: expected,
    timeout_ms: connection.timeout_ms
  };
  pushHistory("generate_test_step", {
    success: true,
    message: "TestStep JSON generated",
    data: generatedTestStepJson.value
  });
  showRawDialog.value = true;
}

function openRangeFor(target: MeasureType) {
  rangeForm.measure = target;
  const range = measureRanges[target];
  rangeForm.min = range?.min ?? null;
  rangeForm.max = range?.max ?? null;
  showRangeDialog.value = true;
}

function saveRange() {
  measureRanges[rangeForm.measure] = {
    ...(rangeForm.min !== null ? { min: Number(rangeForm.min) } : {}),
    ...(rangeForm.max !== null ? { max: Number(rangeForm.max) } : {})
  };
  showRangeDialog.value = false;
}

function clearRange() {
  delete measureRanges[rangeForm.measure];
  rangeForm.min = null;
  rangeForm.max = null;
}

function openExactInput(target: "scale" | "offset") {
  exactTarget.value = target;
  exactValue.value = target === "scale" ? scale.value : offset.value;
  showExactDialog.value = true;
}

function applyExactValue() {
  if (exactTarget.value === "scale") {
    scale.value = Math.max(0.01, Number(exactValue.value));
  } else {
    offset.value = Number(exactValue.value);
  }
  showExactDialog.value = false;
}

function nudgeScale(delta: number) {
  scale.value = roundValue(Math.max(0.01, scale.value + delta));
}

function nudgeOffset(delta: number) {
  offset.value = roundValue(offset.value + delta);
}

function clearScopeState() {
  rawResponse.value = null;
  waveformResponse.value = null;
  generatedTestStepJson.value = null;
  waveformSamples.value = [];
  waveformError.value = "";
  history.value = [];
  for (const key of Object.keys(latestMeasurements) as MeasureType[]) {
    delete latestMeasurements[key];
  }
}

async function copyRawJson() {
  await copyToClipboard(rawJsonText.value);
  notify("positive", "JSON 已复制。");
}

function assertResult(result: ScopeDriverResult) {
  if (result.success) return;
  throw new Error(result.stderr?.trim() || result.message || "Scope 操作失败。");
}

function handleError(error: unknown, action: string, fallback: string) {
  const message = error instanceof Error ? error.message : fallback;
  rawResponse.value = { success: false, message, stderr: message };
  pushHistory(action, rawResponse.value);
  notify("negative", message);
}

function pushHistory(action: string, result: ScopeDriverResult) {
  const data = result.data as Record<string, unknown> | undefined;
  const value = typeof data?.value === "number" ? formatNumber(data.value) : "-";
  const row: HistoryRow = {
    id: Date.now() + Math.random(),
    time: new Date().toLocaleTimeString(),
    action,
    channel: String(data?.channel || channel.value || "-"),
    measure: String(data?.measure || measure.value || "-"),
    value,
    unit: String(data?.unit || unitFor(measure.value) || "-"),
    status: String(data?.status || (result.success ? "ok" : "error")),
    message: result.message || result.stderr || "-"
  };
  history.value = [row, ...history.value].slice(0, 20);
}

function applyMeasurementResult(target: MeasureType, result: ScopeDriverResult) {
  const data = result.data as { value?: number; unit?: string; status?: string; message?: string };
  const value = Number(data?.value);
  if (!Number.isFinite(value)) return;
  const status = data?.status === "passed" ? "PASS" : data?.status === "failed" ? "FAIL" : "UNKNOWN";
  latestMeasurements[target] = {
    value,
    unit: data?.unit || unitFor(target),
    status,
    ...(result.message ? { message: result.message } : {})
  };
}

function normalizeWaveformSamples(data: ScopeWaveformData | undefined) {
  if (!data) return [];
  if (Array.isArray(data.samples) && data.samples.length) {
    return data.samples
      .map(sample => ({ x: Number(sample.x), y: Number(sample.y) }))
      .filter(sample => Number.isFinite(sample.x) && Number.isFinite(sample.y));
  }
  if (Array.isArray(data.preview)) {
    return data.preview
      .map((value, index) => ({ x: index, y: Number(value) }))
      .filter(sample => Number.isFinite(sample.y));
  }
  return [];
}

function samplesToPolyline(samples: ScopeWaveformSample[]) {
  if (samples.length < 2) return "";
  const minX = Math.min(...samples.map(sample => sample.x));
  const maxX = Math.max(...samples.map(sample => sample.x));
  const minY = Math.min(...samples.map(sample => sample.y));
  const maxY = Math.max(...samples.map(sample => sample.y));
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  return samples
    .map(sample => {
      const x = ((sample.x - minX) / spanX) * 920 + 20;
      const y = 460 - ((sample.y - minY) / spanY) * 420;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function mockDetect(): ScopeDriverResult {
  return {
    success: true,
    message: "mock scope connected",
    data: { idn: "MOCK,SIGLENT-SCOPE,FPGA-DEBUG,1.0" },
    stdout: "",
    stderr: ""
  };
}

function mockOk(message: string, data: unknown): ScopeDriverResult {
  return { success: true, message, data, stdout: "", stderr: "" };
}

function mockMeasure(target: MeasureType): ScopeDriverResult {
  const baseValues: Record<MeasureType, number> = {
    vpp: 1.24,
    vmax: 3.31,
    vmin: 0.04,
    vrms: 0.72,
    vavg: 1.65,
    freq: 6_000_000,
    period: 1 / 6_000_000,
    duty: 50.1
  };
  const value = baseValues[target] * (0.985 + Math.random() * 0.03);
  const range = measureRanges[target];
  const status =
    range && (range.min !== undefined || range.max !== undefined)
      ? (range.min === undefined || value >= range.min) && (range.max === undefined || value <= range.max)
        ? "passed"
        : "failed"
      : "unknown";
  return {
    success: true,
    message: `mock ${target} = ${formatNumber(value)} ${unitFor(target)}`,
    data: {
      channel: channel.value,
      measure: target,
      value,
      unit: unitFor(target),
      status
    },
    stdout: "",
    stderr: ""
  };
}

function mockWaveform(): ScopeDriverResult<ScopeWaveformData> {
  const samples = createMockSamples(waveformConfig.preview_points);
  return {
    success: true,
    message: "mock waveform read completed",
    data: {
      channel: channel.value,
      format: "preview",
      encoding: "mock",
      points: waveformConfig.points,
      preview_points: samples.length,
      x_unit: "s",
      y_unit: "V",
      samples
    },
    stdout: "",
    stderr: ""
  };
}

function createMockSamples(count: number) {
  return Array.from({ length: count }, (_, index) => {
    const t = index / Math.max(count - 1, 1);
    const square = Math.sin(t * Math.PI * 8) >= 0 ? 1.2 : -1.2;
    const ripple = Math.sin(t * Math.PI * 32) * 0.08;
    return { x: t * 0.00001, y: square + ripple + offset.value };
  });
}

function unitFor(target: string) {
  if (target === "freq") return "Hz";
  if (target === "period") return "s";
  if (target === "duty") return "%";
  return "V";
}

function formatNumber(value: number) {
  if (!Number.isFinite(value)) return "--";
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(3)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(3)}k`;
  if (Math.abs(value) < 0.001 && value !== 0) return value.toExponential(3);
  return Number(value.toPrecision(5)).toString();
}

function roundValue(value: number) {
  return Math.round(value * 1000) / 1000;
}

function statusBadgeColor(status: string) {
  if (status === "PASS") return "positive";
  if (status === "FAIL") return "negative";
  return "grey-7";
}

function notify(type: "positive" | "negative", message: string) {
  if (typeof $q.notify === "function") {
    $q.notify({ type, message, timeout: 1800 });
  }
}
</script>

<style scoped>
.scope-console-page {
  min-height: 100vh;
  background: #eef2f6;
  color: #111827;
}

.scope-console {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 12px;
  min-height: 100vh;
  padding: 14px;
}

.scope-topbar,
.scope-screen-card,
.scope-control-rack,
.scope-measure-bar {
  border: 1px solid rgba(100, 116, 139, 0.26);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.08);
}

.scope-topbar {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  min-height: 58px;
  padding: 10px 12px;
}

.scope-topbar__brand,
.scope-topbar__identity,
.scope-topbar__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.scope-title {
  font-size: 1.08rem;
  font-weight: 800;
}

.scope-topbar__identity {
  justify-content: center;
  overflow: hidden;
  color: #475569;
  font-size: 0.86rem;
}

.scope-idn {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scope-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 12px;
  min-height: 0;
}

.scope-screen-card {
  display: grid;
  grid-template-rows: minmax(420px, 1fr) auto;
  min-width: 0;
  overflow: hidden;
}

.scope-screen {
  position: relative;
  min-height: 520px;
  overflow: hidden;
  background:
    linear-gradient(rgba(34, 197, 94, 0.13) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 197, 94, 0.13) 1px, transparent 1px),
    #07130f;
  background-size: 48px 48px;
}

.scope-wave-svg {
  width: 100%;
  height: 100%;
  min-height: 520px;
}

.scope-axis {
  stroke: rgba(148, 163, 184, 0.45);
  stroke-width: 1;
}

.scope-trigger {
  stroke: rgba(250, 204, 21, 0.72);
  stroke-dasharray: 8 8;
  stroke-width: 1.4;
}

.scope-wave-line {
  fill: none;
  stroke: #22d3ee;
  stroke-linejoin: round;
  stroke-linecap: round;
  stroke-width: 2.4;
  filter: drop-shadow(0 0 4px rgba(34, 211, 238, 0.55));
}

.scope-screen__corner {
  position: absolute;
  z-index: 2;
  display: grid;
  gap: 3px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(2, 6, 23, 0.68);
  color: #d1fae5;
  font-family: Consolas, monospace;
  font-size: 0.82rem;
}

.scope-screen__corner--left {
  top: 12px;
  left: 12px;
}

.scope-screen__corner--right {
  top: 12px;
  right: 12px;
  text-align: right;
}

.scope-screen__error {
  position: absolute;
  right: 12px;
  bottom: 50px;
  z-index: 3;
  max-width: 46%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scope-screen__empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: rgba(209, 250, 229, 0.78);
  font-family: Consolas, monospace;
}

.scope-screen-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 54px;
  padding: 10px 12px;
  color: #475569;
  font-size: 0.9rem;
}

.scope-screen-footer__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.scope-control-rack {
  display: grid;
  align-content: start;
  gap: 12px;
  padding: 12px;
}

.scope-control-group {
  display: grid;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.24);
}

.scope-control-group:last-child {
  border-bottom: 0;
}

.scope-control-title {
  color: #334155;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.scope-stepper {
  display: grid;
  grid-template-columns: 54px auto minmax(0, 1fr) auto;
  gap: 6px;
  align-items: center;
}

.scope-stepper span {
  color: #64748b;
  font-size: 0.82rem;
}

.scope-value-button {
  min-height: 32px;
  border: 1px solid rgba(100, 116, 139, 0.32);
  border-radius: 6px;
  background: #f8fafc;
  color: #0f172a;
  font-weight: 800;
  cursor: pointer;
}

.scope-panel-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.scope-measure-bar {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  padding: 10px;
}

.scope-measure-tile {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  min-height: 48px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 6px;
  background: #f8fafc;
  color: #0f172a;
  text-align: left;
  cursor: pointer;
}

.scope-measure-tile span {
  color: #64748b;
  font-size: 0.78rem;
  font-weight: 800;
}

.scope-measure-tile strong {
  overflow: hidden;
  font-family: Consolas, monospace;
  font-size: 1rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scope-dialog-card {
  width: min(520px, 92vw);
}

.scope-raw-dialog,
.scope-history-dialog {
  width: min(980px, 94vw);
  max-width: 94vw;
}

.scope-exact-dialog {
  width: min(360px, 90vw);
}

.dialog-title {
  font-size: 1rem;
  font-weight: 800;
}

.dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dialog-grid {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.scope-json-view {
  max-height: 62vh;
  margin: 0;
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  background: #0f172a;
  color: #dbeafe;
  font-family: Consolas, monospace;
  font-size: 0.84rem;
  line-height: 1.5;
}

@media (max-width: 1100px) {
  .scope-topbar,
  .scope-workbench {
    grid-template-columns: 1fr;
  }

  .scope-topbar__identity,
  .scope-topbar__actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .scope-control-rack {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .scope-console {
    padding: 8px;
  }

  .scope-control-rack,
  .scope-measure-bar {
    grid-template-columns: 1fr;
  }

  .scope-screen,
  .scope-wave-svg {
    min-height: 360px;
  }

  .scope-screen__corner--right {
    top: auto;
    right: 12px;
    bottom: 12px;
  }
}
</style>
