<template>
  <q-page class="page">
    <section class="page-section automation-runner">
      <header class="runner-topbar">
        <div>
          <div class="section-kicker">Automation</div>
          <h1 class="section-title">FPGA Test Runner</h1>
        </div>
        <div class="runner-status">
          <q-badge
            outline
            :color="connectionTone.color"
            :label="connectionTone.label"
          />
          <q-badge
            outline
            :color="backendTone.color"
            :label="backendTone.label"
          />
          <q-btn
            flat
            round
            icon="refresh"
            color="primary"
            :loading="loading.refreshing"
            @click="refreshAll"
          >
            <q-tooltip>刷新状态和配置</q-tooltip>
          </q-btn>
        </div>
      </header>

      <section class="surface-block runner-setup">
        <div class="block-head">
          <div>
            <h2 class="block-title">Run Setup</h2>
            <p class="block-subtitle">选择本次运行使用的硬件环境和测试用例。</p>
          </div>
          <div class="runner-actions">
            <q-btn
              flat
              color="primary"
              icon="settings"
              label="编辑 Profile"
              no-caps
              @click="profileDialog = true"
            />
            <q-btn
              flat
              color="primary"
              icon="edit_note"
              label="编辑 Case"
              no-caps
              @click="caseDialog = true"
            />
          </div>
        </div>

        <div class="setup-selector-grid">
          <q-select
            v-model="selectedProfileId"
            outlined
            emit-value
            map-options
            label="Hardware Profile"
            :options="profileOptions"
            :loading="loading.profiles"
          />
          <q-select
            v-model="selectedCaseId"
            outlined
            emit-value
            map-options
            label="Test Case"
            :options="caseOptions"
            :loading="loading.cases"
          />
        </div>

        <div class="setup-summary-grid">
          <div class="summary-panel">
            <div class="summary-panel__label">Hardware Profile</div>
            <div class="summary-panel__title">{{
              selectedProfile?.name || "未选择"
            }}</div>
            <div class="summary-row">
              <span>Board</span>
              <strong>{{ selectedProfile?.board_name || "N/A" }}</strong>
            </div>
            <div class="summary-row">
              <span>UART</span>
              <strong
                >{{ selectedProfile?.uart_port || "未配置" }} ·
                {{ selectedProfile?.uart_baudrate || 115200 }}</strong
              >
            </div>
            <div class="summary-row">
              <span>Scope</span>
              <strong>{{ selectedProfile?.scope_ip || "未配置" }}</strong>
            </div>
          </div>

          <div class="summary-panel">
            <div class="summary-panel__label">Test Case</div>
            <div class="summary-panel__title">{{
              selectedCase?.name || "未选择"
            }}</div>
            <p class="summary-panel__description">{{
              selectedCase?.description || "暂无描述"
            }}</p>
            <div class="summary-row">
              <span>Enabled</span>
              <q-badge
                :color="selectedCase?.enabled ? 'positive' : 'grey-6'"
                :label="selectedCase?.enabled ? 'Yes' : 'No'"
              />
            </div>
            <div class="summary-row">
              <span>Steps</span>
              <strong>{{ steps.length }}</strong>
            </div>
          </div>
        </div>

        <q-expansion-item
          v-model="advancedOpen"
          class="advanced-config"
          icon="tune"
          label="展开高级配置"
          header-class="advanced-config__header"
        >
          <div class="advanced-config__body">
            <div class="form-grid automation-form">
              <q-select
                v-model="profileForm.bit_file"
                outlined
                dense
                emit-value
                map-options
                clearable
                label="Bit File"
                :options="bitFileOptions"
                :display-value="selectedFileName(profileForm.bit_file)"
              />
              <q-select
                v-model="profileForm.elf_file"
                outlined
                dense
                emit-value
                map-options
                clearable
                label="ELF File"
                :options="elfFileOptions"
                :display-value="selectedFileName(profileForm.elf_file)"
              />
              <q-input
                v-model="profileForm.bit_program_channel"
                outlined
                dense
                label="Bit Channel"
              />
              <q-input
                v-model="profileForm.jlink_device"
                outlined
                dense
                label="J-Link Device"
              />
              <q-input
                v-model="profileForm.jlink_interface"
                outlined
                dense
                label="J-Link Interface"
              />
              <q-input
                v-model.number="profileForm.jlink_speed_khz"
                outlined
                dense
                type="number"
                label="J-Link Speed KHz"
              />
              <q-select
                v-model="profileForm.uart_port"
                outlined
                dense
                clearable
                use-input
                hide-selected
                fill-input
                input-debounce="0"
                label="UART Port"
                :options="serialPortOptions"
                @filter="filterSerialPorts"
              />
              <q-input
                v-model.number="profileForm.uart_baudrate"
                outlined
                dense
                type="number"
                label="UART Baudrate"
              />
              <q-input
                v-model="profileForm.scope_ip"
                outlined
                dense
                label="Scope IP"
              />
              <q-input
                v-model="profileForm.scope_channel"
                outlined
                dense
                label="Scope Channel"
              />
            </div>
            <div class="button-row">
              <q-btn
                unelevated
                color="primary"
                icon="save"
                label="保存高级配置"
                no-caps
                :loading="loading.savingProfile"
                @click="saveProfile"
              />
              <q-btn
                flat
                round
                icon="cable"
                color="grey-8"
                :loading="loading.ports"
                @click="loadSerialPorts"
              >
                <q-tooltip>刷新串口</q-tooltip>
              </q-btn>
            </div>
          </div>
        </q-expansion-item>
      </section>

      <section class="surface-block test-flow-panel">
        <div class="block-head">
          <div>
            <h2 class="block-title">Test Flow</h2>
            <p class="block-subtitle">{{
              steps.length
                ? `${steps.length} 个步骤将按顺序执行。`
                : "当前 Test Case 还没有 Step。"
            }}</p>
          </div>
          <q-btn
            unelevated
            color="primary"
            icon="add"
            label="添加 Step"
            no-caps
            :disable="!selectedCaseId"
            @click="stepDialog = true"
          />
        </div>

        <div v-if="!steps.length" class="records-empty flow-empty">
          选择 Test Case 后，在这里添加测试步骤。
        </div>

        <q-timeline
          v-else
          color="primary"
          layout="comfortable"
          class="flow-timeline"
        >
          <q-timeline-entry
            v-for="(item, index) in flowSteps"
            :key="item.step.id"
            :icon="stepStatusIcon(item.status)"
            :color="stepBadgeColor(item.status)"
          >
            <article class="flow-step-card">
              <div class="flow-step-card__head">
                <div class="flow-step-card__main">
                  <div class="flow-step-card__index">Step {{ index + 1 }}</div>
                  <h3>{{ item.step.name }}</h3>
                  <div class="flow-step-card__meta">
                    <q-badge
                      outline
                      color="grey-8"
                      :label="item.step.step_type"
                    />
                    <span
                      >{{ formatDuration(item.step.timeout_ms) }} timeout</span
                    >
                    <q-badge
                      outline
                      :color="
                        item.step.continue_on_failure ? 'warning' : 'grey-7'
                      "
                      :label="
                        item.step.continue_on_failure ? '失败继续' : '失败停止'
                      "
                    />
                    <span>{{ item.durationLabel }}</span>
                  </div>
                </div>
                <q-badge
                  rounded
                  :color="stepBadgeColor(item.status)"
                  text-color="white"
                  :label="item.status"
                />
              </div>

              <div v-if="item.error" class="flow-step-card__error">{{
                item.error
              }}</div>
              <div v-else-if="item.message" class="flow-step-card__message">{{
                item.message
              }}</div>

              <pre v-if="item.output" class="log-console step-output">{{
                item.output
              }}</pre>

              <div class="flow-step-card__actions">
                <q-btn
                  flat
                  round
                  dense
                  icon="keyboard_arrow_up"
                  :disable="index === 0 || loading.reorderingStep"
                  @click="moveStep(index, -1)"
                >
                  <q-tooltip>上移</q-tooltip>
                </q-btn>
                <q-btn
                  flat
                  round
                  dense
                  icon="keyboard_arrow_down"
                  :disable="
                    index === steps.length - 1 || loading.reorderingStep
                  "
                  @click="moveStep(index, 1)"
                >
                  <q-tooltip>下移</q-tooltip>
                </q-btn>
                <q-btn
                  flat
                  round
                  dense
                  icon="delete"
                  color="negative"
                  @click="deleteStep(item.step.id)"
                >
                  <q-tooltip>删除 Step</q-tooltip>
                </q-btn>
              </div>
            </article>
          </q-timeline-entry>
        </q-timeline>
      </section>

      <section class="surface-block run-control-panel">
        <div class="block-head">
          <div>
            <h2 class="block-title">Run Control</h2>
            <p class="block-subtitle"
              >执行当前选择的 Profile 和 Case，并跟踪实时结果。</p
            >
          </div>
          <q-badge
            rounded
            :color="runTone.color"
            text-color="white"
            :label="runTone.label"
          />
        </div>

        <div class="run-control-layout">
          <div>
            <div class="status-line" :class="`status-line--${runTone.state}`">{{
              statusMessage
            }}</div>
            <q-linear-progress
              v-if="currentRun"
              :value="currentRun.progress_percent / 100"
              color="primary"
              track-color="grey-3"
              class="execution-progress"
            />
            <div v-if="currentRun" class="run-meta">
              <span>状态: {{ currentRun.status }}</span>
              <span
                >进度: {{ currentRun.completed_steps }}/{{
                  currentRun.total_steps
                }}</span
              >
              <span v-if="currentRun.queue_position"
                >排队: 第 {{ currentRun.queue_position }} 位</span
              >
              <span v-if="currentRun.current_step_name"
                >当前步骤: {{ currentRun.current_step_name }}</span
              >
            </div>
          </div>

          <div class="run-control-actions">
            <q-btn
              unelevated
              size="lg"
              color="primary"
              icon="play_arrow"
              label="Start Run"
              no-caps
              :loading="loading.running"
              :disable="!canRun"
              @click="runSelectedCase"
            />
            <q-btn
              flat
              color="negative"
              icon="stop"
              label="Stop"
              no-caps
              :disable="!canStop"
              @click="stopCurrentRun"
            />
          </div>
        </div>
      </section>
    </section>

    <q-dialog v-model="profileDialog">
      <q-card class="runner-dialog">
        <q-card-section class="dialog-head">
          <div>
            <div class="section-kicker">Configuration</div>
            <h2 class="block-title">Hardware Profile</h2>
          </div>
          <q-btn flat round icon="close" v-close-popup />
        </q-card-section>
        <q-card-section class="form-grid automation-form">
          <q-input v-model="profileForm.name" outlined dense label="Name" />
          <q-input
            v-model="profileForm.board_name"
            outlined
            dense
            label="Board"
          />
          <q-input
            v-model="profileForm.description"
            outlined
            dense
            label="Description"
          />
          <q-select
            v-model="profileForm.bit_file"
            outlined
            dense
            emit-value
            map-options
            clearable
            label="Bit File"
            :options="bitFileOptions"
            :display-value="selectedFileName(profileForm.bit_file)"
          />
          <q-select
            v-model="profileForm.elf_file"
            outlined
            dense
            emit-value
            map-options
            clearable
            label="ELF File"
            :options="elfFileOptions"
            :display-value="selectedFileName(profileForm.elf_file)"
          />
          <q-input
            v-model="profileForm.jlink_device"
            outlined
            dense
            label="J-Link Device"
          />
          <q-input
            v-model="profileForm.uart_port"
            outlined
            dense
            label="UART Port"
          />
          <q-input
            v-model="profileForm.scope_ip"
            outlined
            dense
            label="Scope IP"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="取消" no-caps v-close-popup />
          <q-btn
            unelevated
            color="primary"
            icon="save"
            label="保存 Profile"
            no-caps
            :loading="loading.savingProfile"
            @click="saveProfile"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="caseDialog">
      <q-card class="runner-dialog">
        <q-card-section class="dialog-head">
          <div>
            <div class="section-kicker">Configuration</div>
            <h2 class="block-title">Test Case</h2>
          </div>
          <q-btn flat round icon="close" v-close-popup />
        </q-card-section>
        <q-card-section class="form-grid automation-form">
          <q-input v-model="caseForm.name" outlined dense label="Case Name" />
          <q-input
            v-model="caseForm.description"
            outlined
            dense
            label="Description"
          />
          <q-toggle
            v-model="caseForm.enabled"
            label="Enabled"
            color="primary"
          />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="取消" no-caps v-close-popup />
          <q-btn
            unelevated
            color="primary"
            icon="save"
            label="保存 Case"
            no-caps
            :loading="loading.savingCase"
            @click="saveCase"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="stepDialog">
      <q-card class="runner-dialog runner-dialog--wide">
        <q-card-section class="dialog-head">
          <div>
            <div class="section-kicker">Test Flow</div>
            <h2 class="block-title">添加 Step</h2>
          </div>
          <q-btn flat round icon="close" v-close-popup />
        </q-card-section>
        <q-card-section class="step-editor">
          <div class="form-grid">
            <q-input
              v-model.number="stepForm.order_index"
              outlined
              dense
              type="number"
              label="Order"
            />
            <q-select
              v-model="stepForm.step_type"
              outlined
              dense
              label="Step Type"
              :options="stepTypes"
            />
            <q-input v-model="stepForm.name" outlined dense label="Step Name" />
            <q-input
              v-model.number="stepForm.timeout_ms"
              outlined
              dense
              type="number"
              label="Timeout ms"
            />
            <q-toggle
              v-model="stepForm.continue_on_failure"
              label="失败后继续"
              color="warning"
            />
          </div>
          <div class="json-grid">
            <q-input
              v-model="stepForm.configText"
              outlined
              type="textarea"
              label="config_json"
              autogrow
            />
            <q-input
              v-model="stepForm.expectedText"
              outlined
              type="textarea"
              label="expected_json"
              autogrow
            />
          </div>
        </q-card-section>
        <q-card-actions align="between">
          <q-btn
            flat
            color="grey-8"
            icon="content_copy"
            label="填入示例"
            no-caps
            @click="fillStepExample"
          />
          <div>
            <q-btn flat label="取消" no-caps v-close-popup />
            <q-btn
              unelevated
              color="primary"
              icon="add"
              label="添加 Step"
              no-caps
              :loading="loading.savingStep"
              :disable="!selectedCaseId"
              @click="saveStep"
            />
          </div>
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch
} from "vue";

type HardwareProfile = {
  id: number;
  name: string;
  description: string | null;
  board_name: string | null;
  bit_file: string | null;
  bit_program_channel: string | null;
  elf_file: string | null;
  jlink_interface: string | null;
  jlink_device: string | null;
  jlink_speed_khz: number | null;
  uart_port: string | null;
  uart_baudrate: number;
  scope_ip: string | null;
  scope_channel: string | null;
};

type TestCase = {
  id: number;
  name: string;
  description: string | null;
  enabled: boolean;
};

type TestStep = {
  id: number;
  order_index: number;
  step_type: string;
  name: string;
  config_json?: Record<string, unknown>;
  expected_json?: Record<string, unknown>;
  timeout_ms: number;
  continue_on_failure: boolean;
};

type StepResult = {
  id: number;
  order_index: number;
  step_name: string | null;
  step_type: string | null;
  status: string;
  message: string | null;
  stdout: string | null;
  stderr: string | null;
  duration_ms?: number | null;
  test_step_id?: number | null;
};

type TestRunDetail = {
  id: number;
  run_id?: number;
  status: string;
  summary: string | null;
  error_message: string | null;
  total_steps: number;
  completed_steps: number;
  progress_percent: number;
  queue_position: number | null;
  current_step_name: string | null;
  steps: StepResult[];
};

type SerialPortResponse = {
  items: Array<{ device: string; description?: string | null }>;
};

type UploadedFile = {
  filename: string;
  path: string;
};

type FileOption = {
  label: string;
  value: string;
};

const stepTypes = [
  "program_bit",
  "program_elf",
  "uart_wait",
  "uart_query",
  "sleep",
  "scope_measure",
  "assert_value",
  "assert_text"
];

const profiles = ref<HardwareProfile[]>([]);
const testCases = ref<TestCase[]>([]);
const steps = ref<TestStep[]>([]);
const serialPorts = ref<SerialPortResponse["items"]>([]);
const serialPortOptions = ref<string[]>([]);
const bitFileOptions = ref<FileOption[]>([]);
const elfFileOptions = ref<FileOption[]>([]);
const selectedProfileId = ref<number | null>(null);
const selectedCaseId = ref<number | null>(null);
const currentRun = ref<TestRunDetail | null>(null);
const statusMessage = ref("选择 Hardware Profile 和 Test Case 后执行。");
const backendStatus = ref<"checking" | "ok" | "error">("checking");
const advancedOpen = ref(false);
const profileDialog = ref(false);
const caseDialog = ref(false);
const stepDialog = ref(false);
let pollTimer: number | null = null;

const loading = reactive({
  profiles: false,
  cases: false,
  ports: false,
  savingProfile: false,
  savingCase: false,
  savingStep: false,
  reorderingStep: false,
  refreshing: false,
  running: false
});

const profileForm = reactive({
  name: "local-cw310",
  description: "",
  board_name: "CW310",
  board_serial: "",
  bit_file: "artifacts/bitstreams/lowrisc_systems_chip.bit",
  bit_program_channel: "",
  elf_file: "artifacts/firmware/testbench_case1.elf",
  jlink_serial: "",
  jlink_interface: "JTAG",
  jlink_device: "RISC-V",
  jlink_speed_khz: 4000,
  uart_port: "",
  uart_baudrate: 115200,
  uart_bytesize: 8,
  uart_parity: "N",
  uart_stopbits: 1,
  uart_timeout_ms: 1000,
  scope_model: "",
  scope_ip: "",
  scope_port: null as number | null,
  scope_channel: "CH1"
});

const caseForm = reactive({
  name: "program_and_uart_check",
  description: "Program FPGA/ELF, then query UART.",
  enabled: true
});

const stepForm = reactive({
  order_index: 1,
  step_type: "sleep",
  name: "等待设备稳定",
  timeout_ms: 30000,
  continue_on_failure: false,
  configText: '{\n  "seconds": 1\n}',
  expectedText: "{}"
});

const profileOptions = computed(() =>
  profiles.value.map(profile => ({
    label: `${profile.id}. ${profile.name}`,
    value: profile.id
  }))
);

const caseOptions = computed(() =>
  testCases.value.map(testCase => ({
    label: `${testCase.id}. ${testCase.name}`,
    value: testCase.id
  }))
);

const selectedProfile = computed(
  () => profiles.value.find(item => item.id === selectedProfileId.value) ?? null
);
const selectedCase = computed(
  () => testCases.value.find(item => item.id === selectedCaseId.value) ?? null
);
const canRun = computed(() =>
  Boolean(selectedProfileId.value && selectedCaseId.value && steps.value.length)
);
const canStop = computed(() =>
  Boolean(
    currentRun.value &&
    ["waiting", "running", "stopping"].includes(currentRun.value.status)
  )
);

const runSteps = computed(() => currentRun.value?.steps ?? []);
const connectionTone = computed(() => {
  if (
    currentRun.value &&
    ["waiting", "running", "stopping"].includes(currentRun.value.status)
  ) {
    return { color: "primary", label: "Connected · Active" };
  }
  if (selectedProfileId.value)
    return { color: "positive", label: "Profile Ready" };
  return { color: "grey-6", label: "No Profile" };
});
const backendTone = computed(() => {
  if (backendStatus.value === "ok")
    return { color: "positive", label: "Backend OK" };
  if (backendStatus.value === "error")
    return { color: "negative", label: "Backend Error" };
  return { color: "grey-6", label: "Backend Checking" };
});
const flowSteps = computed(() =>
  steps.value.map(step => {
    const result = runSteps.value.find(
      item =>
        item.test_step_id === step.id || item.order_index === step.order_index
    );
    const isCurrent =
      currentRun.value?.current_step_name === step.name &&
      currentRun.value?.status === "running";
    const status = result?.status ?? (isCurrent ? "running" : "pending");
    const output = [result?.stdout, result?.stderr].filter(Boolean).join("\n");
    return {
      step,
      result,
      status,
      message: result?.message || null,
      error: ["failed", "error"].includes(status)
        ? result?.message || result?.stderr || "Step 执行失败"
        : null,
      output,
      durationLabel: result?.duration_ms
        ? formatDuration(result.duration_ms)
        : "未执行"
    };
  })
);

const runTone = computed(() => {
  if (!currentRun.value)
    return { state: "idle", color: "grey-6", label: "Idle" };
  if (currentRun.value.status === "waiting")
    return { state: "running", color: "grey-6", label: "Waiting" };
  if (currentRun.value.status === "stopping")
    return { state: "running", color: "warning", label: "Stopping" };
  if (currentRun.value.status === "passed")
    return { state: "success", color: "positive", label: "Passed" };
  if (currentRun.value.status === "failed")
    return { state: "error", color: "negative", label: "Failed" };
  if (currentRun.value.status === "stopped")
    return { state: "error", color: "grey-7", label: "Stopped" };
  if (currentRun.value.status === "error")
    return { state: "error", color: "negative", label: "Error" };
  return { state: "running", color: "primary", label: currentRun.value.status };
});

watch(selectedProfileId, profileId => {
  const profile = profiles.value.find(item => item.id === profileId);
  if (profile) applyProfile(profile);
});

watch(selectedCaseId, async caseId => {
  const testCase = testCases.value.find(item => item.id === caseId);
  if (testCase) {
    caseForm.name = testCase.name;
    caseForm.description = testCase.description ?? "";
    caseForm.enabled = testCase.enabled;
  }
  await loadSteps();
});

async function loadProfiles() {
  loading.profiles = true;
  try {
    const response = await fetch("/api/hardware-profiles");
    profiles.value = (await response.json()) as HardwareProfile[];
    if (!selectedProfileId.value && profiles.value[0])
      selectedProfileId.value = profiles.value[0].id;
  } finally {
    loading.profiles = false;
  }
}

async function loadHealth() {
  backendStatus.value = "checking";
  try {
    const response = await fetch("/api/health");
    backendStatus.value = response.ok ? "ok" : "error";
  } catch {
    backendStatus.value = "error";
  }
}

async function refreshAll() {
  loading.refreshing = true;
  try {
    await Promise.all([
      loadHealth(),
      loadProfiles(),
      loadCases(),
      loadUploadedFiles(),
      loadSerialPorts()
    ]);
    if (currentRun.value) await pollCurrentRun();
  } finally {
    loading.refreshing = false;
  }
}

async function loadCases() {
  loading.cases = true;
  try {
    const response = await fetch("/api/test-cases");
    testCases.value = (await response.json()) as TestCase[];
    if (!selectedCaseId.value && testCases.value[0])
      selectedCaseId.value = testCases.value[0].id;
  } finally {
    loading.cases = false;
  }
}

async function loadSteps() {
  if (!selectedCaseId.value) {
    steps.value = [];
    statusMessage.value = "先选择一个 Test Case。";
    return;
  }
  const response = await fetch(`/api/test-cases/${selectedCaseId.value}/steps`);
  steps.value = (await response.json()) as TestStep[];
  stepForm.order_index = steps.value.length
    ? Math.max(...steps.value.map(step => step.order_index)) + 1
    : 1;
  if (!steps.value.length) {
    statusMessage.value =
      "当前 Case 还没有 Step。填写右侧表单后，点“添加 Step”。";
    return;
  }
  if (!selectedProfileId.value) {
    statusMessage.value =
      "Step 已加载，再选择一个 Hardware Profile 就可以运行。";
    return;
  }
  statusMessage.value = `已加载 ${steps.value.length} 个 Step，可以执行。`;
}

async function loadSerialPorts() {
  loading.ports = true;
  try {
    const response = await fetch("/api/serial-ports");
    const data = (await response.json()) as SerialPortResponse;
    serialPorts.value = data.items;
    serialPortOptions.value = data.items.map(port => port.device);
  } finally {
    loading.ports = false;
  }
}

async function loadUploadedFiles() {
  const response = await fetch("/api/uploads");
  const data = (await response.json()) as {
    bit?: UploadedFile[];
    elf?: UploadedFile[];
  };
  bitFileOptions.value = normalizeFileOptions(data.bit ?? []);
  elfFileOptions.value = normalizeFileOptions(data.elf ?? []);
}

function normalizeFileOptions(files: UploadedFile[]): FileOption[] {
  return files.map(file => ({
    label: file.filename,
    value: file.path
  }));
}

function selectedFileName(value: string | null | undefined) {
  if (!value) return "";
  const option = [...bitFileOptions.value, ...elfFileOptions.value].find(
    item => item.value === value
  );
  return option?.label ?? fileName(value);
}

function fileName(value: string) {
  return value.split(/[\\/]/).filter(Boolean).pop() ?? value;
}

function filterSerialPorts(
  value: string,
  update: (callback: () => void) => void
) {
  update(() => {
    const needle = value.toLowerCase();
    serialPortOptions.value = serialPorts.value
      .map(port => port.device)
      .filter(device => device.toLowerCase().includes(needle));
  });
}

async function saveProfile() {
  loading.savingProfile = true;
  try {
    const method = selectedProfileId.value ? "PUT" : "POST";
    const url = selectedProfileId.value
      ? `/api/hardware-profiles/${selectedProfileId.value}`
      : "/api/hardware-profiles";
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profileForm)
    });
    if (!response.ok) throw new Error(await response.text());
    const saved = (await response.json()) as HardwareProfile;
    await loadProfiles();
    selectedProfileId.value = saved.id;
    statusMessage.value = `Profile #${saved.id} 已保存。`;
    profileDialog.value = false;
  } catch (error) {
    statusMessage.value = formatError(error);
  } finally {
    loading.savingProfile = false;
  }
}

async function saveCase() {
  loading.savingCase = true;
  try {
    const method = selectedCaseId.value ? "PUT" : "POST";
    const url = selectedCaseId.value
      ? `/api/test-cases/${selectedCaseId.value}`
      : "/api/test-cases";
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(caseForm)
    });
    if (!response.ok) throw new Error(await response.text());
    const saved = (await response.json()) as TestCase;
    await loadCases();
    selectedCaseId.value = saved.id;
    statusMessage.value = `Case #${saved.id} 已保存。`;
    caseDialog.value = false;
  } catch (error) {
    statusMessage.value = formatError(error);
  } finally {
    loading.savingCase = false;
  }
}

async function saveStep() {
  if (!selectedCaseId.value) return;
  loading.savingStep = true;
  try {
    const payload = {
      order_index: stepForm.order_index,
      step_type: stepForm.step_type,
      name: stepForm.name,
      timeout_ms: stepForm.timeout_ms,
      continue_on_failure: stepForm.continue_on_failure,
      config_json: JSON.parse(stepForm.configText || "{}") as Record<
        string,
        unknown
      >,
      expected_json: JSON.parse(stepForm.expectedText || "{}") as Record<
        string,
        unknown
      >
    };
    const response = await fetch(
      `/api/test-cases/${selectedCaseId.value}/steps`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      }
    );
    if (!response.ok) throw new Error(await response.text());
    await loadSteps();
    statusMessage.value = "Step 已添加，现在可以执行了。";
    stepDialog.value = false;
  } catch (error) {
    statusMessage.value = formatError(error);
  } finally {
    loading.savingStep = false;
  }
}

async function deleteStep(stepId: number) {
  const response = await fetch(`/api/test-steps/${stepId}`, {
    method: "DELETE"
  });
  if (response.ok) await loadSteps();
}

async function moveStep(index: number, direction: -1 | 1) {
  const targetIndex = index + direction;
  const current = steps.value[index];
  const target = steps.value[targetIndex];
  if (!current || !target) return;

  loading.reorderingStep = true;
  const currentOrder = current.order_index;
  const targetOrder = target.order_index;
  const tempOrder = -Date.now();
  try {
    await updateStepOrder(current, tempOrder);
    await updateStepOrder(target, currentOrder);
    await updateStepOrder(current, targetOrder);
    await loadSteps();
    statusMessage.value = "Step 顺序已更新。";
  } catch (error) {
    statusMessage.value = formatError(error);
    await loadSteps();
  } finally {
    loading.reorderingStep = false;
  }
}

async function updateStepOrder(step: TestStep, orderIndex: number) {
  const response = await fetch(`/api/test-steps/${step.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      order_index: orderIndex,
      step_type: step.step_type,
      name: step.name,
      config_json: step.config_json ?? {},
      expected_json: step.expected_json ?? {},
      timeout_ms: step.timeout_ms,
      continue_on_failure: step.continue_on_failure ?? false
    })
  });
  if (!response.ok) throw new Error(await response.text());
}

async function runSelectedCase() {
  if (!selectedProfileId.value || !selectedCaseId.value) return;
  loading.running = true;
  currentRun.value = null;
  statusMessage.value = "正在加入执行队列...";
  try {
    const response = await fetch("/api/test-runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        hardware_profile_id: selectedProfileId.value,
        test_case_id: selectedCaseId.value
      })
    });
    if (!response.ok) throw new Error(await response.text());
    currentRun.value = (await response.json()) as TestRunDetail;
    statusMessage.value =
      currentRun.value.summary ||
      `Run #${currentRun.value.id} ${currentRun.value.status}`;
    startPolling();
  } catch (error) {
    statusMessage.value = formatError(error);
  } finally {
    loading.running = false;
  }
}

async function stopCurrentRun() {
  if (!currentRun.value) return;
  try {
    const response = await fetch(`/api/test-runs/${currentRun.value.id}/stop`, {
      method: "POST"
    });
    if (!response.ok) throw new Error(await response.text());
    currentRun.value = (await response.json()) as TestRunDetail;
    statusMessage.value = currentRun.value.summary || "停止请求已发送。";
    startPolling();
  } catch (error) {
    statusMessage.value = formatError(error);
  }
}

function startPolling() {
  stopPolling();
  void pollCurrentRun();
  pollTimer = window.setInterval(() => {
    void pollCurrentRun();
  }, 1200);
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function pollCurrentRun() {
  if (!currentRun.value) return;
  const response = await fetch(`/api/test-runs/${currentRun.value.id}`);
  if (!response.ok) return;
  currentRun.value = (await response.json()) as TestRunDetail;
  statusMessage.value =
    currentRun.value.summary ||
    `Run #${currentRun.value.id} ${currentRun.value.status}`;
  if (!["waiting", "running", "stopping"].includes(currentRun.value.status)) {
    stopPolling();
  }
}

function fillStepExample() {
  const examples: Record<
    string,
    { name: string; config: object; expected: object }
  > = {
    program_bit: {
      name: "烧录 FPGA bit",
      config: { use_profile_bit: true },
      expected: { success: true }
    },
    program_elf: {
      name: "烧录 ELF",
      config: { use_profile_elf: true },
      expected: { success: true }
    },
    uart_wait: {
      name: "等待 UART READY",
      config: {
        contains: "READY",
        read_timeout_ms: 10000,
        encoding: "utf-8"
      },
      expected: {}
    },
    uart_query: {
      name: "UART 查询",
      config: {
        command: "audio start",
        append_newline: true,
        read_timeout_ms: 3000,
        encoding: "utf-8"
      },
      expected: { contains: "OK" }
    },
    sleep: { name: "等待设备稳定", config: { seconds: 1 }, expected: {} },
    scope_measure: {
      name: "示波器测量 VPP",
      config: { channel: "CH1", measure: "vpp" },
      expected: { min: 0.2, max: 3.0 }
    },
    assert_value: {
      name: "数值断言",
      config: { value: 1 },
      expected: { min: 0, max: 2 }
    },
    assert_text: {
      name: "文本断言",
      config: { text: "OK" },
      expected: { contains: "OK" }
    }
  };
  const example = examples[stepForm.step_type] ??
    examples.sleep ?? {
      name: "等待设备稳定",
      config: { seconds: 1 },
      expected: {}
    };
  stepForm.name = example.name;
  stepForm.continue_on_failure = false;
  stepForm.configText = JSON.stringify(example.config, null, 2);
  stepForm.expectedText = JSON.stringify(example.expected, null, 2);
}

function applyProfile(profile: HardwareProfile) {
  profileForm.name = profile.name;
  profileForm.description = profile.description ?? "";
  profileForm.board_name = profile.board_name ?? "";
  profileForm.bit_file = profile.bit_file ?? "";
  profileForm.bit_program_channel = profile.bit_program_channel ?? "";
  profileForm.elf_file = profile.elf_file ?? "";
  profileForm.jlink_interface = profile.jlink_interface ?? "JTAG";
  profileForm.jlink_device = profile.jlink_device ?? "";
  profileForm.jlink_speed_khz = profile.jlink_speed_khz ?? 4000;
  profileForm.uart_port = profile.uart_port ?? "";
  profileForm.uart_baudrate = profile.uart_baudrate ?? 115200;
  profileForm.scope_ip = profile.scope_ip ?? "";
  profileForm.scope_channel = profile.scope_channel ?? "CH1";
}

function stepBadgeColor(status: string) {
  if (status === "passed" || status === "pass") return "positive";
  if (status === "failed" || status === "fail" || status === "error")
    return "negative";
  if (status === "skipped") return "grey-6";
  if (status === "pending") return "grey-5";
  return "primary";
}

function stepStatusIcon(status: string) {
  if (status === "passed" || status === "pass") return "check";
  if (status === "failed" || status === "fail" || status === "error")
    return "close";
  if (status === "running") return "play_arrow";
  if (status === "skipped") return "skip_next";
  return "radio_button_unchecked";
}

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes}m ${rest}s`;
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : "操作失败。";
}

onMounted(() => {
  refreshAll();
  fillStepExample();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>
