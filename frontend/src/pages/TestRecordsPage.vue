<template>
  <q-page class="page">
    <section class="page-section">
      <div class="section-head">
        <div class="section-kicker">Records</div>
        <h1 class="section-title">Test Run Records</h1>
      </div>

      <div class="records-grid">
        <section class="surface-block">
          <div class="block-head">
            <h2 class="block-title">Runs</h2>
            <q-btn
              flat
              round
              icon="refresh"
              color="primary"
              :loading="isLoadingRuns"
              @click="loadRuns"
            >
              <q-tooltip>刷新记录</q-tooltip>
            </q-btn>
          </div>

          <q-list bordered separator class="case-list">
            <q-item
              v-for="run in runs"
              :key="run.id"
              clickable
              :active="selectedRunId === run.id"
              active-class="sidebar-item--active"
              @click="selectRun(run.id)"
            >
              <q-item-section>
                <q-item-label>{{ run.name || `Run #${run.id}` }}</q-item-label>
                <q-item-label caption>{{
                  formatTimestamp(run.created_at)
                }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <div class="records-run-side">
                  <q-badge
                    rounded
                    :color="runBadgeColor(run.status)"
                    text-color="white"
                    :label="run.status"
                  />
                  <q-btn
                    v-if="canStop(run.status)"
                    flat
                    round
                    dense
                    icon="stop"
                    color="negative"
                    @click.stop="stopRun(run.id)"
                  >
                    <q-tooltip>停止任务</q-tooltip>
                  </q-btn>
                </div>
              </q-item-section>
            </q-item>
          </q-list>
        </section>

        <section class="surface-block">
          <div class="block-head">
            <h2 class="block-title">Details</h2>
            <q-badge
              rounded
              :color="
                selectedRun ? runBadgeColor(selectedRun.status) : 'grey-6'
              "
              text-color="white"
              :label="selectedRun?.status ?? 'Idle'"
            />
          </div>

          <div v-if="!selectedRun" class="blank-state records-placeholder">
            <div>
              <div class="blank-state__title">No record selected</div>
              <div class="blank-state__text"
                >Pick a run from the list to inspect it.</div
              >
            </div>
          </div>

          <div v-else class="records-detail">
            <div class="records-summary">
              <div
                ><strong>Name:</strong>
                {{ selectedRun.name || `Run #${selectedRun.id}` }}</div
              >
              <div><strong>Status:</strong> {{ selectedRun.status }}</div>
              <div
                ><strong>Summary:</strong>
                {{ selectedRun.summary || "None" }}</div
              >
              <div
                ><strong>Duration:</strong>
                {{ selectedRun.duration_ms ?? 0 }} ms</div
              >
              <div
                ><strong>Progress:</strong>
                {{ selectedRun.progress_percent ?? 0 }}%</div
              >
              <div
                ><strong>Started:</strong>
                {{ formatTimestamp(selectedRun.started_at) }}</div
              >
              <div
                ><strong>Finished:</strong>
                {{ formatTimestamp(selectedRun.finished_at) }}</div
              >
              <div
                ><strong>Profile:</strong>
                {{ selectedRun.hardware_profile_id ?? "None" }}</div
              >
              <div
                ><strong>Case:</strong>
                {{ selectedRun.test_case_id ?? "None" }}</div
              >
            </div>

            <q-linear-progress
              :value="(selectedRun.progress_percent ?? 0) / 100"
              color="primary"
              track-color="grey-3"
              class="execution-progress"
            />

            <q-tabs
              v-model="activeTab"
              dense
              active-color="primary"
              indicator-color="primary"
              no-caps
            >
              <q-tab name="steps" label="Step Results" />
              <q-tab name="snapshots" label="Snapshots" />
            </q-tabs>

            <q-tab-panels v-model="activeTab" animated class="log-tabs">
              <q-tab-panel name="steps" class="log-tabs__panel records-panel">
                <div v-if="!selectedRun.steps.length" class="records-empty"
                  >No step results recorded.</div
                >
                <div v-else class="step-stack">
                  <article
                    v-for="step in selectedRun.steps"
                    :key="step.id"
                    class="step-item"
                  >
                    <div class="step-item__head">
                      <strong
                        >{{ step.order_index }}.
                        {{ step.step_name || step.name }}</strong
                      >
                      <q-badge
                        rounded
                        :color="runBadgeColor(step.status)"
                        text-color="white"
                        :label="step.status"
                      />
                    </div>
                    <div class="step-item__body">{{
                      step.message || step.step_type || step.type
                    }}</div>
                    <pre
                      v-if="step.stdout || step.stderr"
                      class="log-console step-output"
                      >{{
                        [step.stdout, step.stderr].filter(Boolean).join("\n")
                      }}</pre
                    >
                  </article>
                </div>
              </q-tab-panel>

              <q-tab-panel
                name="snapshots"
                class="log-tabs__panel records-panel"
              >
                <div class="snapshot-grid">
                  <div>
                    <div class="uploaded-file-heading">Hardware Profile</div>
                    <pre class="log-console records-log">{{
                      stringify(selectedRun.profile_snapshot_json)
                    }}</pre>
                  </div>
                  <div>
                    <div class="uploaded-file-heading">Test Case</div>
                    <pre class="log-console records-log">{{
                      stringify(selectedRun.case_snapshot_json)
                    }}</pre>
                  </div>
                </div>
              </q-tab-panel>
            </q-tab-panels>
          </div>
        </section>
      </div>
    </section>
  </q-page>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

type StepResult = {
  id: number;
  order_index: number;
  step_name: string | null;
  step_type: string | null;
  name: string | null;
  type: string | null;
  status: string;
  message: string | null;
  stdout: string | null;
  stderr: string | null;
};

type TestRun = {
  id: number;
  name: string | null;
  status: string;
  summary: string | null;
  hardware_profile_id: number | null;
  test_case_id: number | null;
  profile_snapshot_json: unknown;
  case_snapshot_json: unknown;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  total_steps?: number;
  completed_steps?: number;
  progress_percent?: number;
  queue_position?: number | null;
  current_step_name?: string | null;
  created_at: string | null;
  steps: StepResult[];
};

type RunListItem = Omit<TestRun, "steps"> & { steps?: StepResult[] };

type ActiveTab = "steps" | "snapshots";

const runs = ref<RunListItem[]>([]);
const selectedRunId = ref<number | null>(null);
const selectedRun = ref<TestRun | null>(null);
const isLoadingRuns = ref(false);
const activeTab = ref<ActiveTab>("steps");
let pollTimer: number | null = null;

async function loadRuns() {
  isLoadingRuns.value = true;
  try {
    const response = await fetch("/api/test-runs");
    runs.value = (await response.json()) as RunListItem[];
    const firstRun = runs.value[0];
    if (!selectedRunId.value && firstRun) await selectRun(firstRun.id);
  } finally {
    isLoadingRuns.value = false;
  }
}

async function selectRun(runId: number) {
  selectedRunId.value = runId;
  const response = await fetch(`/api/test-runs/${runId}`);
  selectedRun.value = (await response.json()) as TestRun;
  startPolling();
}

function formatTimestamp(value: string | null) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function runBadgeColor(status: string) {
  if (status === "passed") return "positive";
  if (status === "failed" || status === "error") return "negative";
  if (status === "running" || status === "pending") return "primary";
  if (status === "waiting") return "grey-6";
  if (status === "stopping") return "warning";
  if (status === "stopped") return "grey-7";
  return "grey-6";
}

function canStop(status: string) {
  return ["waiting", "running", "stopping"].includes(status);
}

async function stopRun(runId: number) {
  const response = await fetch(`/api/test-runs/${runId}/stop`, {
    method: "POST"
  });
  if (!response.ok) return;
  await loadRuns();
  if (selectedRunId.value === runId) {
    selectedRun.value = (await response.json()) as TestRun;
    startPolling();
  }
}

function startPolling() {
  stopPolling();
  pollTimer = window.setInterval(() => {
    void refreshSelectedRun();
  }, 1500);
}

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function refreshSelectedRun() {
  if (!selectedRunId.value) return;
  await loadRuns();
  const response = await fetch(`/api/test-runs/${selectedRunId.value}`);
  if (!response.ok) return;
  selectedRun.value = (await response.json()) as TestRun;
  if (!selectedRun.value || !canStop(selectedRun.value.status)) {
    stopPolling();
  }
}

function stringify(value: unknown) {
  if (value === null || value === undefined) return "No snapshot.";
  return JSON.stringify(sanitizeFilePathsForDisplay(value), null, 2);
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

function fileName(value: string) {
  return value.split(/[\\/]/).filter(Boolean).pop() ?? value;
}

onMounted(() => {
  loadRuns();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>
