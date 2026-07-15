<template>
  <q-page class="page">
    <section class="page-section">
        <div class="section-head">
          <div class="section-kicker">Upload</div>
          <h1 class="section-title">File Management</h1>
        </div>

      <div class="upload-grid">
        <section class="surface-block">
          <div class="block-head">
            <h2 class="block-title">Bitstream</h2>
            <q-badge rounded color="primary" text-color="white" label=".bit" />
          </div>

          <q-file
            v-model="bitFile"
            outlined
            dense
            clearable
            label="Select File"
          >
            <template #prepend>
              <q-icon name="memory" />
            </template>
          </q-file>

          <div class="button-row">
            <q-btn
              color="primary"
              text-color="white"
              unelevated
              no-caps
              icon="upload_file"
              label="Upload File"
              :loading="uploadingType === 'bit'"
              :disable="!bitFile || uploadingType !== null"
              @click="uploadSelectedFile('bit')"
            />
          </div>

          <div v-if="uploadingType === 'bit'" class="upload-progress">
            <div class="upload-progress__meta">
              <span>{{ uploadProgress.bit }}%</span>
              <span>{{ uploadProgressLabel("bit") }}</span>
            </div>
            <q-linear-progress
              :value="uploadProgress.bit / 100"
              color="primary"
              track-color="grey-3"
              rounded
            />
          </div>
        </section>

        <section class="surface-block">
          <div class="block-head">
            <h2 class="block-title">Firmware</h2>
            <q-badge rounded color="primary" text-color="white" label=".elf" />
          </div>

          <q-file
            v-model="elfFile"
            outlined
            dense
            clearable
            label="Select File"
          >
            <template #prepend>
              <q-icon name="developer_board" />
            </template>
          </q-file>

          <div class="button-row">
            <q-btn
              color="primary"
              text-color="white"
              unelevated
              no-caps
              icon="upload_file"
              label="Upload File"
              :loading="uploadingType === 'elf'"
              :disable="!elfFile || uploadingType !== null"
              @click="uploadSelectedFile('elf')"
            />
          </div>

          <div v-if="uploadingType === 'elf'" class="upload-progress">
            <div class="upload-progress__meta">
              <span>{{ uploadProgress.elf }}%</span>
              <span>{{ uploadProgressLabel("elf") }}</span>
            </div>
            <q-linear-progress
              :value="uploadProgress.elf / 100"
              color="primary"
              track-color="grey-3"
              rounded
            />
          </div>
        </section>

        <section class="surface-block upload-grid__wide">
          <div class="block-head">
            <h2 class="block-title">Test Run</h2>
            <q-badge
              rounded
              color="primary"
              text-color="white"
              label=".yaml / .yml"
            />
          </div>

          <p class="block-subtitle">
            Files uploaded here are saved into <code>artifacts/testruns</code>.
            YAML files can then be imported into a hardware profile, a test
            case, and a queued test run.
          </p>

          <q-file
            v-model="testrunFile"
            outlined
            dense
            clearable
            label="Select File"
          >
            <template #prepend>
              <q-icon name="playlist_add_check_circle" />
            </template>
          </q-file>

          <div class="button-row">
            <q-btn
              color="primary"
              text-color="white"
              unelevated
              no-caps
              icon="upload_file"
              label="Upload File"
              :loading="uploadingType === 'testrun'"
              :disable="!testrunFile || uploadingType !== null"
              @click="uploadSelectedFile('testrun')"
            />
            <q-btn
              color="secondary"
              text-color="white"
              unelevated
              no-caps
              icon="play_arrow"
              label="Upload And Run"
              :loading="uploadingType === 'testrun-run'"
              :disable="!testrunFile || uploadingType !== null"
              @click="uploadSelectedFile('testrun', true)"
            />
            <q-btn
              outline
              no-caps
              color="primary"
              icon="download"
              label="下载示例 YAML"
              tag="a"
              href="/examples/uart_echo_test.sample.yaml"
              download="uart_echo_test.sample.yaml"
            />
          </div>

          <div
            v-if="
              uploadingType === 'testrun' || uploadingType === 'testrun-run'
            "
            class="upload-progress"
          >
            <div class="upload-progress__meta">
              <span>{{ uploadProgress[uploadingType] }}%</span>
              <span>{{ uploadProgressLabel(uploadingType) }}</span>
            </div>
            <q-linear-progress
              :value="uploadProgress[uploadingType] / 100"
              color="primary"
              track-color="grey-3"
              rounded
            />
          </div>
        </section>

        <section class="surface-block upload-grid__wide">
          <div class="block-head">
            <h2 class="block-title">Uploaded Files</h2>
            <q-btn
              flat
              round
              icon="refresh"
              color="primary"
              :loading="isLoadingFiles"
              @click="loadUploadedFiles"
            >
              <q-tooltip>Refresh files</q-tooltip>
            </q-btn>
          </div>

          <div class="uploaded-file-columns">
            <div>
              <div class="uploaded-file-heading">Bitstreams</div>
              <q-list bordered separator class="case-list">
                <q-item v-for="file in uploadedFiles.bit" :key="file.path">
                  <q-item-section>
                    <q-item-label>{{ file.filename }}</q-item-label>
                  </q-item-section>
                  <q-item-section side class="upload-file-actions">
                    <span>{{ formatSize(file.size) }}</span>
                    <q-btn
                      flat
                      dense
                      round
                      color="negative"
                      icon="delete"
                      :disable="isBusyForActions"
                      @click="deleteUploadedFile('bit', file.filename)"
                    >
                      <q-tooltip>Delete file</q-tooltip>
                    </q-btn>
                  </q-item-section>
                </q-item>
              </q-list>
            </div>

            <div>
              <div class="uploaded-file-heading">Firmware</div>
              <q-list bordered separator class="case-list">
                <q-item v-for="file in uploadedFiles.elf" :key="file.path">
                  <q-item-section>
                    <q-item-label>{{ file.filename }}</q-item-label>
                  </q-item-section>
                  <q-item-section side class="upload-file-actions">
                    <span>{{ formatSize(file.size) }}</span>
                    <q-btn
                      flat
                      dense
                      round
                      color="negative"
                      icon="delete"
                      :disable="isBusyForActions"
                      @click="deleteUploadedFile('elf', file.filename)"
                    >
                      <q-tooltip>Delete file</q-tooltip>
                    </q-btn>
                  </q-item-section>
                </q-item>
              </q-list>
            </div>

            <div>
              <div class="uploaded-file-heading">Test Runs</div>
              <q-list bordered separator class="case-list">
                <q-item v-for="file in uploadedFiles.testrun" :key="file.path">
                  <q-item-section>
                    <q-item-label>{{ file.filename }}</q-item-label>
                  </q-item-section>
                  <q-item-section side class="upload-file-actions">
                    <span>{{ formatSize(file.size) }}</span>
                    <q-btn
                      flat
                      dense
                      no-caps
                      color="secondary"
                      icon="play_arrow"
                      label="Import & Run"
                      :loading="importingFilename === file.filename"
                      :disable="
                        uploadingType !== null || importingFilename !== null
                      "
                      @click="importUploadedTestRun(file.filename)"
                    />
                    <q-btn
                      flat
                      dense
                      round
                      color="negative"
                      icon="delete"
                      :disable="isBusyForActions"
                      @click="deleteUploadedFile('testrun', file.filename)"
                    >
                      <q-tooltip>Delete file</q-tooltip>
                    </q-btn>
                  </q-item-section>
                </q-item>
              </q-list>
            </div>
          </div>
        </section>
      </div>
    </section>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useQuasar } from "quasar";

type UploadType = "bit" | "elf" | "testrun" | "testrun-run";
type UploadedFileType = "bit" | "elf" | "testrun";

type UploadedFile = {
  filename: string;
  path: string;
  size: number;
};

const $q = useQuasar();

const bitFile = ref<File | null>(null);
const elfFile = ref<File | null>(null);
const testrunFile = ref<File | null>(null);
const uploadingType = ref<UploadType | null>(null);
const importingFilename = ref<string | null>(null);
const deletingFileKey = ref<string | null>(null);
const isLoadingFiles = ref(false);
const uploadProgress = reactive<Record<UploadType, number>>({
  bit: 0,
  elf: 0,
  testrun: 0,
  "testrun-run": 0
});
const uploadTransferred = reactive<Record<UploadType, number>>({
  bit: 0,
  elf: 0,
  testrun: 0,
  "testrun-run": 0
});
const uploadTotals = reactive<Record<UploadType, number>>({
  bit: 0,
  elf: 0,
  testrun: 0,
  "testrun-run": 0
});

const uploadedFiles = reactive<Record<UploadedFileType, UploadedFile[]>>({
  bit: [],
  elf: [],
  testrun: []
});

const isBusyForActions = computed(
  () =>
    uploadingType.value !== null ||
    importingFilename.value !== null ||
    deletingFileKey.value !== null
);

async function uploadSelectedFile(type: UploadType, autoImport = false) {
  const file =
    type === "bit"
      ? bitFile.value
      : type === "elf"
        ? elfFile.value
        : testrunFile.value;
  if (!file) return;

  const uploadType = autoImport ? "testrun-run" : type;

  uploadingType.value = uploadType;
  uploadProgress[uploadType] = 0;
  uploadTransferred[uploadType] = 0;
  uploadTotals[uploadType] = file.size;

  try {
    const result = (await uploadBinaryFile(
      type === "testrun-run" ? "testrun" : type,
      file,
      uploadType
    )) as UploadedFile;
    $q.notify({
      type: "positive",
      message: `Uploaded ${result.filename}`
    });
    if (autoImport && type === "testrun") {
      const run = await importUploadedTestRun(result.filename, false);
      $q.notify({
        type: "positive",
        message: `Queued run #${run.id}: ${run.name}`
      });
    }
    if (type === "bit") bitFile.value = null;
    if (type === "elf") elfFile.value = null;
    if (type === "testrun") testrunFile.value = null;
    await loadUploadedFiles();
  } catch (error) {
    $q.notify({
      type: "negative",
      message: error instanceof Error ? error.message : "Upload failed"
    });
  } finally {
    uploadProgress[uploadType] = 0;
    uploadTransferred[uploadType] = 0;
    uploadTotals[uploadType] = 0;
    uploadingType.value = null;
  }
}

function uploadBinaryFile(
  type: UploadedFileType,
  file: File,
  progressType: UploadType = type
): Promise<UploadedFile> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(
      "POST",
      `/api/uploads/${type}?filename=${encodeURIComponent(file.name)}`
    );
    request.setRequestHeader("Content-Type", "application/octet-stream");
    request.setRequestHeader("X-Filename", file.name);

    request.upload.onprogress = event => {
      if (!event.lengthComputable) return;
      uploadTransferred[progressType] = event.loaded;
      uploadTotals[progressType] = event.total;
      uploadProgress[progressType] = Math.max(
        0,
        Math.min(100, Math.round((event.loaded / event.total) * 100))
      );
    };

    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        try {
          resolve(JSON.parse(request.responseText) as UploadedFile);
        } catch (error) {
          reject(error);
        }
        return;
      }
      reject(
        new Error(
          request.responseText || `Upload failed with status ${request.status}`
        )
      );
    };

    request.onerror = () => {
      reject(new Error("Network error during upload"));
    };

    request.send(file);
  });
}

async function loadUploadedFiles() {
  isLoadingFiles.value = true;
  try {
    const response = await fetch("/api/uploads");
    const data = (await response.json()) as Record<
      UploadedFileType,
      UploadedFile[]
    >;
    uploadedFiles.bit = data.bit ?? [];
    uploadedFiles.elf = data.elf ?? [];
    uploadedFiles.testrun = data.testrun ?? [];
  } finally {
    isLoadingFiles.value = false;
  }
}

async function deleteUploadedFile(type: UploadedFileType, filename: string) {
  deletingFileKey.value = `${type}:${filename}`;
  try {
    const response = await fetch(
      `/api/uploads/${type}/${encodeURIComponent(filename)}`,
      {
        method: "DELETE"
      }
    );
    const data = (await response.json()) as { detail?: string };
    if (!response.ok) {
      throw new Error(data.detail || "Delete file failed");
    }
    $q.notify({
      type: "positive",
      message: `Deleted ${filename}`
    });
    await loadUploadedFiles();
  } catch (error) {
    $q.notify({
      type: "negative",
      message: error instanceof Error ? error.message : "Delete file failed"
    });
  } finally {
    deletingFileKey.value = null;
  }
}

type ImportedRun = {
  id: number;
  name: string;
};

async function importUploadedTestRun(filename: string, notify = true) {
  importingFilename.value = filename;
  try {
    const response = await fetch("/api/uploads/testrun/import", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ filename })
    });

    const data = (await response.json()) as {
      run?: ImportedRun;
      detail?: string;
    };

    if (!response.ok || !data.run) {
      throw new Error(data.detail || "Import YAML failed");
    }

    if (notify) {
      $q.notify({
        type: "positive",
        message: `Queued run #${data.run.id}: ${data.run.name}`
      });
    }
    return data.run;
  } catch (error) {
    if (notify) {
      $q.notify({
        type: "negative",
        message: error instanceof Error ? error.message : "Import YAML failed"
      });
    }
    throw error;
  } finally {
    importingFilename.value = null;
  }
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function uploadProgressLabel(type: UploadType) {
  const total = uploadTotals[type];
  const transferred = uploadTransferred[type];
  if (!total) return "Preparing upload";
  return `${formatSize(transferred)} / ${formatSize(total)}`;
}

onMounted(() => {
  loadUploadedFiles();
});
</script>
