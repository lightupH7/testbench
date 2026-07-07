<template>
  <q-page class="page">
    <section class="page-section">
      <div class="section-head">
        <div class="section-kicker">Upload</div>
        <h1 class="section-title">Upload Test Files</h1>
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
            accept=".bit"
            label="Select Bit File"
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
              label="Upload Bit"
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
            accept=".elf"
            label="Select ELF File"
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
              label="Upload ELF"
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
            <h2 class="block-title">Case</h2>
            <q-badge rounded color="grey-6" text-color="white" label="Later" />
          </div>

          <div class="blank-state upload-case-placeholder">
            <div>
              <div class="blank-state__title">Case upload is not configured yet</div>
              <div class="blank-state__text">
                This area is reserved for importing automated test cases later.
              </div>
            </div>
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
                    <q-item-label caption>{{ file.path }}</q-item-label>
                  </q-item-section>
                  <q-item-section side>{{ formatSize(file.size) }}</q-item-section>
                </q-item>
              </q-list>
            </div>

            <div>
              <div class="uploaded-file-heading">Firmware</div>
              <q-list bordered separator class="case-list">
                <q-item v-for="file in uploadedFiles.elf" :key="file.path">
                  <q-item-section>
                    <q-item-label>{{ file.filename }}</q-item-label>
                    <q-item-label caption>{{ file.path }}</q-item-label>
                  </q-item-section>
                  <q-item-section side>{{ formatSize(file.size) }}</q-item-section>
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
import { onMounted, reactive, ref } from "vue";
import { useQuasar } from "quasar";

type UploadType = "bit" | "elf";

type UploadedFile = {
  filename: string;
  path: string;
  size: number;
};

const $q = useQuasar();

const bitFile = ref<File | null>(null);
const elfFile = ref<File | null>(null);
const uploadingType = ref<UploadType | null>(null);
const isLoadingFiles = ref(false);
const uploadProgress = reactive<Record<UploadType, number>>({
  bit: 0,
  elf: 0
});
const uploadTransferred = reactive<Record<UploadType, number>>({
  bit: 0,
  elf: 0
});
const uploadTotals = reactive<Record<UploadType, number>>({
  bit: 0,
  elf: 0
});

const uploadedFiles = reactive<Record<UploadType, UploadedFile[]>>({
  bit: [],
  elf: []
});

async function uploadSelectedFile(type: UploadType) {
  const file = type === "bit" ? bitFile.value : elfFile.value;
  if (!file) return;

  uploadingType.value = type;
  uploadProgress[type] = 0;
  uploadTransferred[type] = 0;
  uploadTotals[type] = file.size;

  try {
    const result = (await uploadBinaryFile(type, file)) as UploadedFile;
    $q.notify({
      type: "positive",
      message: `Uploaded ${result.path}`
    });
    if (type === "bit") bitFile.value = null;
    if (type === "elf") elfFile.value = null;
    await loadUploadedFiles();
  } catch (error) {
    $q.notify({
      type: "negative",
      message: error instanceof Error ? error.message : "Upload failed"
    });
  } finally {
    uploadProgress[type] = 0;
    uploadTransferred[type] = 0;
    uploadTotals[type] = 0;
    uploadingType.value = null;
  }
}

function uploadBinaryFile(type: UploadType, file: File): Promise<UploadedFile> {
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
      uploadTransferred[type] = event.loaded;
      uploadTotals[type] = event.total;
      uploadProgress[type] = Math.max(
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
    const data = (await response.json()) as Record<UploadType, UploadedFile[]>;
    uploadedFiles.bit = data.bit ?? [];
    uploadedFiles.elf = data.elf ?? [];
  } finally {
    isLoadingFiles.value = false;
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
