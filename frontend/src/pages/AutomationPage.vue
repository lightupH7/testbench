<template>
  <q-page class="page">
    <section class="page-section">
      <div class="section-head">
        <div class="section-kicker">Automation</div>
        <h1 class="section-title">FPGA Test Runner</h1>
      </div>

      <div class="automation-grid automation-grid--mvp">
        <section class="surface-block">
          <div class="block-head">
            <h2 class="block-title">Hardware Profile</h2>
            <q-btn flat round icon="refresh" color="primary" :loading="loading.profiles" @click="loadProfiles">
              <q-tooltip>刷新 Profile</q-tooltip>
            </q-btn>
          </div>

          <q-select
            v-model="selectedProfileId"
            outlined
            dense
            emit-value
            map-options
            label="选择硬件环境"
            :options="profileOptions"
          />

          <div class="form-grid automation-form">
            <q-input v-model="profileForm.name" outlined dense label="Name" />
            <q-input v-model="profileForm.board_name" outlined dense label="Board" />
            <q-input v-model="profileForm.bit_file" outlined dense label="Bit File" />
            <q-input v-model="profileForm.elf_file" outlined dense label="ELF File" />
            <q-input v-model="profileForm.bit_program_channel" outlined dense label="Bit Channel" />
            <q-input v-model="profileForm.jlink_device" outlined dense label="J-Link Device" />
            <q-input v-model="profileForm.jlink_interface" outlined dense label="J-Link Interface" />
            <q-input v-model.number="profileForm.jlink_speed_khz" outlined dense type="number" label="J-Link Speed KHz" />
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
            <q-input v-model.number="profileForm.uart_baudrate" outlined dense type="number" label="UART Baudrate" />
            <q-input v-model="profileForm.scope_ip" outlined dense label="Scope IP" />
            <q-input v-model="profileForm.scope_channel" outlined dense label="Scope Channel" />
          </div>

          <div class="button-row">
            <q-btn unelevated color="primary" icon="save" label="保存 Profile" no-caps :loading="loading.savingProfile" @click="saveProfile" />
            <q-btn flat round icon="cable" color="grey-8" :loading="loading.ports" @click="loadSerialPorts">
              <q-tooltip>刷新串口</q-tooltip>
            </q-btn>
          </div>
        </section>

        <section class="surface-block">
          <div class="block-head">
            <h2 class="block-title">Test Case</h2>
            <q-btn flat round icon="refresh" color="primary" :loading="loading.cases" @click="loadCases">
              <q-tooltip>刷新 Case</q-tooltip>
            </q-btn>
          </div>

          <q-select
            v-model="selectedCaseId"
            outlined
            dense
            emit-value
            map-options
            label="选择测试用例"
            :options="caseOptions"
          />

          <div class="form-grid automation-form">
            <q-input v-model="caseForm.name" outlined dense label="Case Name" />
            <q-input v-model="caseForm.description" outlined dense label="Description" />
          </div>

          <div class="button-row">
            <q-btn unelevated color="primary" icon="save" label="保存 Case" no-caps :loading="loading.savingCase" @click="saveCase" />
          </div>

          <q-separator class="automation-separator" />

          <div class="block-head">
            <h2 class="block-title">Steps</h2>
            <q-badge rounded color="grey-7" text-color="white" :label="`${steps.length} steps`" />
          </div>

          <div class="step-editor">
            <div class="form-grid">
              <q-input v-model.number="stepForm.order_index" outlined dense type="number" label="Order" />
              <q-select v-model="stepForm.step_type" outlined dense label="Step Type" :options="stepTypes" />
              <q-input v-model="stepForm.name" outlined dense label="Step Name" />
              <q-input v-model.number="stepForm.timeout_ms" outlined dense type="number" label="Timeout ms" />
            </div>

            <div class="json-grid">
              <q-input v-model="stepForm.configText" outlined type="textarea" label="config_json" autogrow />
              <q-input v-model="stepForm.expectedText" outlined type="textarea" label="expected_json" autogrow />
            </div>

            <div class="button-row">
              <q-btn unelevated color="primary" icon="add" label="添加 Step" no-caps :loading="loading.savingStep" :disable="!selectedCaseId" @click="saveStep" />
              <q-btn flat color="grey-8" icon="content_copy" label="填入示例" no-caps @click="fillStepExample" />
            </div>
          </div>

          <q-list bordered separator class="case-list automation-step-list">
            <q-item v-for="step in steps" :key="step.id">
              <q-item-section>
                <q-item-label>{{ step.order_index }}. {{ step.name }}</q-item-label>
                <q-item-label caption>{{ step.step_type }} · {{ step.timeout_ms }} ms</q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-btn flat round dense icon="delete" color="negative" @click="deleteStep(step.id)">
                  <q-tooltip>删除 Step</q-tooltip>
                </q-btn>
              </q-item-section>
            </q-item>
          </q-list>
        </section>

        <section class="surface-block automation-run-panel">
          <div class="block-head">
            <h2 class="block-title">Run Result</h2>
            <q-badge rounded :color="runTone.color" text-color="white" :label="runTone.label" />
          </div>

          <div class="status-line" :class="`status-line--${runTone.state}`">{{ statusMessage }}</div>

          <div class="button-row">
            <q-btn
              unelevated
              color="primary"
              icon="play_arrow"
              label="加入队列"
              no-caps
              :loading="loading.running"
              :disable="!canRun"
              @click="runSelectedCase"
            />
            <q-btn
              flat
              color="negative"
              icon="stop"
              label="停止"
              no-caps
              :disable="!canStop"
              @click="stopCurrentRun"
            />
          </div>

          <q-linear-progress
            v-if="currentRun"
            :value="currentRun.progress_percent / 100"
            color="primary"
            track-color="grey-3"
            class="execution-progress"
          />

          <div v-if="currentRun" class="run-meta">
            <span>状态: {{ currentRun.status }}</span>
            <span>进度: {{ currentRun.completed_steps }}/{{ currentRun.total_steps }}</span>
            <span v-if="currentRun.queue_position">排队: 第 {{ currentRun.queue_position }} 位</span>
            <span v-if="currentRun.current_step_name">当前步骤: {{ currentRun.current_step_name }}</span>
          </div>

          <div v-if="!steps.length" class="records-empty">
            当前 Case 还没有已保存的 Step。右侧填写后，还需要点一次“添加 Step”。
          </div>

          <div class="step-stack">
            <article v-for="result in runSteps" :key="result.id" class="step-item">
              <div class="step-item__head">
                <strong>{{ result.order_index }}. {{ result.step_name }}</strong>
                <q-badge rounded :color="stepBadgeColor(result.status)" text-color="white" :label="result.status" />
              </div>
              <div class="step-item__body">{{ result.message || result.step_type }}</div>
              <pre v-if="result.stdout || result.stderr" class="log-console step-output">{{ [result.stdout, result.stderr].filter(Boolean).join('\n') }}</pre>
            </article>
          </div>
        </section>
      </div>
    </section>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

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
  timeout_ms: number;
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

const stepTypes = [
  "program_bit",
  "program_elf",
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
const selectedProfileId = ref<number | null>(null);
const selectedCaseId = ref<number | null>(null);
const currentRun = ref<TestRunDetail | null>(null);
const statusMessage = ref("选择 Hardware Profile 和 Test Case 后执行。");
let pollTimer: number | null = null;

const loading = reactive({
  profiles: false,
  cases: false,
  ports: false,
  savingProfile: false,
  savingCase: false,
  savingStep: false,
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
  configText: '{\n  "seconds": 1\n}',
  expectedText: "{}"
});

const profileOptions = computed(() =>
  profiles.value.map(profile => ({ label: `${profile.id}. ${profile.name}`, value: profile.id }))
);

const caseOptions = computed(() =>
  testCases.value.map(testCase => ({ label: `${testCase.id}. ${testCase.name}`, value: testCase.id }))
);

const canRun = computed(() => Boolean(selectedProfileId.value && selectedCaseId.value && steps.value.length));
const canStop = computed(() => Boolean(currentRun.value && ["waiting", "running", "stopping"].includes(currentRun.value.status)));

const runSteps = computed(() => currentRun.value?.steps ?? []);

const runTone = computed(() => {
  if (!currentRun.value) return { state: "idle", color: "grey-6", label: "Idle" };
  if (currentRun.value.status === "waiting") return { state: "running", color: "grey-6", label: "Waiting" };
  if (currentRun.value.status === "stopping") return { state: "running", color: "warning", label: "Stopping" };
  if (currentRun.value.status === "passed") return { state: "success", color: "positive", label: "Passed" };
  if (currentRun.value.status === "failed") return { state: "error", color: "negative", label: "Failed" };
  if (currentRun.value.status === "stopped") return { state: "error", color: "grey-7", label: "Stopped" };
  if (currentRun.value.status === "error") return { state: "error", color: "negative", label: "Error" };
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
    if (!selectedProfileId.value && profiles.value[0]) selectedProfileId.value = profiles.value[0].id;
  } finally {
    loading.profiles = false;
  }
}

async function loadCases() {
  loading.cases = true;
  try {
    const response = await fetch("/api/test-cases");
    testCases.value = (await response.json()) as TestCase[];
    if (!selectedCaseId.value && testCases.value[0]) selectedCaseId.value = testCases.value[0].id;
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
  stepForm.order_index = steps.value.length ? Math.max(...steps.value.map(step => step.order_index)) + 1 : 1;
  if (!steps.value.length) {
    statusMessage.value = "当前 Case 还没有 Step。填写右侧表单后，点“添加 Step”。";
    return;
  }
  if (!selectedProfileId.value) {
    statusMessage.value = "Step 已加载，再选择一个 Hardware Profile 就可以运行。";
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

function filterSerialPorts(value: string, update: (callback: () => void) => void) {
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
    const url = selectedCaseId.value ? `/api/test-cases/${selectedCaseId.value}` : "/api/test-cases";
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
      config_json: JSON.parse(stepForm.configText || "{}") as Record<string, unknown>,
      expected_json: JSON.parse(stepForm.expectedText || "{}") as Record<string, unknown>
    };
    const response = await fetch(`/api/test-cases/${selectedCaseId.value}/steps`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(await response.text());
    await loadSteps();
    statusMessage.value = "Step 已添加，现在可以执行了。";
  } catch (error) {
    statusMessage.value = formatError(error);
  } finally {
    loading.savingStep = false;
  }
}

async function deleteStep(stepId: number) {
  const response = await fetch(`/api/test-steps/${stepId}`, { method: "DELETE" });
  if (response.ok) await loadSteps();
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
    statusMessage.value = currentRun.value.summary || `Run #${currentRun.value.id} ${currentRun.value.status}`;
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
    const response = await fetch(`/api/test-runs/${currentRun.value.id}/stop`, { method: "POST" });
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
  statusMessage.value = currentRun.value.summary || `Run #${currentRun.value.id} ${currentRun.value.status}`;
  if (!["waiting", "running", "stopping"].includes(currentRun.value.status)) {
    stopPolling();
  }
}

function fillStepExample() {
  const examples: Record<string, { name: string; config: object; expected: object }> = {
    program_bit: { name: "烧录 FPGA bit", config: { use_profile_bit: true }, expected: { success: true } },
    program_elf: { name: "烧录 ELF", config: { use_profile_elf: true }, expected: { success: true } },
    uart_query: {
      name: "UART 查询",
      config: { command: "audio start", append_newline: true, read_timeout_ms: 3000, encoding: "utf-8" },
      expected: { contains: "OK" }
    },
    sleep: { name: "等待设备稳定", config: { seconds: 1 }, expected: {} },
    scope_measure: { name: "示波器测量 VPP", config: { channel: "CH1", measure: "vpp" }, expected: { min: 0.2, max: 3.0 } },
    assert_value: { name: "数值断言", config: { value: 1 }, expected: { min: 0, max: 2 } },
    assert_text: { name: "文本断言", config: { text: "OK" }, expected: { contains: "OK" } }
  };
  const example = examples[stepForm.step_type] ?? examples.sleep ?? {
    name: "等待设备稳定",
    config: { seconds: 1 },
    expected: {}
  };
  stepForm.name = example.name;
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
  if (status === "passed") return "positive";
  if (status === "failed" || status === "error") return "negative";
  return "primary";
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : "操作失败。";
}

onMounted(() => {
  loadProfiles();
  loadCases();
  loadSerialPorts();
  fillStepExample();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>
