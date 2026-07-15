<template>
  <q-page class="page">
    <section class="page-section">
      <div class="section-head">
        <div class="section-kicker">Console</div>
        <h1 class="section-title">控制台</h1>
      </div>

      <div class="console-layout">
        <section class="surface-block serial-control console-panel">
          <div class="block-head">
            <div>
              <h2 class="block-title">串口控制台</h2>
              <p class="serial-panel-caption">
                选择串口参数并建立连接，支持自定义波特率和帧格式。
              </p>
            </div>
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

          <div class="serial-settings-panel">
            <div class="serial-settings-card">
              <div class="serial-settings-card__title">连接参数</div>
              <div class="form-grid serial-settings-grid">
                <q-select
                  v-model="form.port"
                  outlined
                  dense
                  emit-value
                  map-options
                  label="串口"
                  :loading="isLoadingPorts"
                  :options="portOptions"
                />

                <q-select
                  v-model.number="form.baudrate"
                  outlined
                  dense
                  emit-value
                  map-options
                  label="波特率"
                  :options="baudrateOptions"
                />

                <q-select
                  v-model.number="form.bytesize"
                  outlined
                  dense
                  emit-value
                  map-options
                  label="数据位"
                  :options="bytesizeOptions"
                />

                <q-select
                  v-model="form.parity"
                  outlined
                  dense
                  emit-value
                  map-options
                  label="校验位"
                  :options="parityOptions"
                />

                <q-select
                  v-model.number="form.stopbits"
                  outlined
                  dense
                  emit-value
                  map-options
                  label="停止位"
                  :options="stopbitsOptions"
                />

                <div class="serial-baudrate-editor">
                  <q-input
                    v-model.number="customBaudrate"
                    outlined
                    dense
                    type="number"
                    label="自定义波特率"
                    min="1"
                  />
                  <q-btn
                    color="secondary"
                    text-color="white"
                    unelevated
                    no-caps
                    icon="bookmark_add"
                    :disable="!canSaveCustomBaudrate"
                    label="保存"
                    @click="saveCustomBaudrate"
                  />
                </div>
              </div>
            </div>

            <div class="serial-settings-card">
              <div class="serial-settings-card__title">收发格式</div>
              <div class="serial-quick-grid">
                <q-select
                  v-model="form.receiveFormat"
                  outlined
                  dense
                  emit-value
                  map-options
                  label="接收显示"
                  :options="formatOptions"
                />

                <q-select
                  v-model="form.sendFormat"
                  outlined
                  dense
                  emit-value
                  map-options
                  label="发送格式"
                  :options="formatOptions"
                />
              </div>
            </div>
          </div>

          <div class="button-row serial-toolbar">
            <q-btn
              color="primary"
              text-color="white"
              unelevated
              no-caps
              :icon="uartConnected ? 'link_off' : 'settings_input_component'"
              :disable="!canToggleConnection"
              :loading="isTogglingConnection"
              :label="uartConnected ? '关闭串口' : '打开串口'"
              @click="toggleUart"
            >
              <q-tooltip>{{
                uartConnected ? "关闭当前串口连接" : "按当前参数打开串口"
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
              <q-tooltip>刷新串口列表</q-tooltip>
            </q-btn>
          </div>

          <div class="status-line" :class="`status-line--${statusTone}`">
            {{ statusMessage }}
          </div>

          <div class="serial-send-panel">
            <div class="serial-settings-card__title">发送数据</div>
            <q-input
              v-model="sendText"
              class="serial-send-input"
              outlined
              autogrow
              type="textarea"
              label="输入要发送的数据"
            />

            <div class="serial-send-actions">
              <q-toggle v-model="appendNewline" dense label="自动追加换行" />
              <div class="serial-send-actions__buttons">
                <q-btn
                  color="primary"
                  text-color="white"
                  unelevated
                  no-caps
                  icon="send"
                  :disable="!canSend"
                  label="发送"
                  @click="sendUart"
                />
                <q-btn
                  flat
                  round
                  icon="backspace"
                  color="grey-8"
                  @click="sendText = ''"
                >
                  <q-tooltip>清空输入</q-tooltip>
                </q-btn>
              </div>
            </div>
          </div>
        </section>

        <section class="surface-block manual-program-panel console-panel console-wide">
          <div class="block-head">
            <div>
              <h2 class="block-title">手动烧录</h2>
              <p class="serial-panel-caption">
                将 bit/ELF 烧录动作合并到控制台里，和串口调试放在同一工作区。
              </p>
            </div>
            <div class="block-head__badges">
              <q-badge
                rounded
                :color="manualStreamConnected ? 'positive' : 'grey-6'"
                text-color="white"
                :label="
                  manualStreamConnected ? 'Live Stream On' : 'Live Stream Off'
                "
              />
              <q-badge
                rounded
                :color="manualResultTone.color"
                text-color="white"
                :label="manualResultTone.label"
              />
            </div>
          </div>

          <div class="manual-program-grid">
            <div class="serial-settings-card">
              <div class="block-head manual-program-head">
                <div>
                  <div class="serial-settings-card__title">烧录参数</div>
                  <p class="manual-program-note">
                    支持单独烧录 bit、单独烧录 ELF，或按顺序一起执行。
                  </p>
                </div>
                <q-btn
                  flat
                  round
                  icon="health_and_safety"
                  color="primary"
                  :loading="isCheckingManualHealth"
                  @click="checkManualHealth"
                >
                  <q-tooltip>检查后端状态</q-tooltip>
                </q-btn>
              </div>

              <q-btn-toggle
                v-model="manualForm.action"
                class="action-switch"
                no-caps
                spread
                unelevated
                toggle-color="primary"
                text-color="grey-8"
                :options="manualActionOptions"
              />

              <div class="form-grid manual-form-grid">
                <q-select
                  v-if="manualNeedsBit"
                  v-model="manualForm.bit_file"
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
                  :display-value="selectedFileName(manualForm.bit_file)"
                  @filter="filterBitOptions"
                />

                <q-select
                  v-if="manualNeedsElf"
                  v-model="manualForm.elf_file"
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
                  :display-value="selectedFileName(manualForm.elf_file)"
                  @filter="filterElfOptions"
                />

                <q-input
                  v-if="manualNeedsBit"
                  v-model="manualForm.vivado_path"
                  outlined
                  dense
                  label="Vivado"
                  placeholder="vivado"
                />

                <q-input
                  v-if="manualNeedsBit"
                  v-model="manualForm.hw_server_url"
                  outlined
                  dense
                  clearable
                  label="HW Server"
                  placeholder="localhost:3121"
                />

                <q-input
                  v-if="manualNeedsElf"
                  v-model="manualForm.device"
                  outlined
                  dense
                  clearable
                  label="Device"
                  placeholder="RISC-V"
                />

                <q-select
                  v-if="manualNeedsElf"
                  v-model="manualForm.interface"
                  outlined
                  dense
                  emit-value
                  map-options
                  label="Interface"
                  :options="manualInterfaceOptions"
                />

                <q-input
                  v-if="manualNeedsElf"
                  v-model.number="manualForm.speed"
                  type="number"
                  outlined
                  dense
                  label="Speed"
                />

                <q-input
                  v-model.number="manualForm.timeout"
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
                  <q-tooltip>刷新文件列表</q-tooltip>
                </q-btn>
                <q-btn
                  color="primary"
                  text-color="white"
                  unelevated
                  no-caps
                  icon="play_arrow"
                  :loading="isSubmittingManual"
                  :disable="!canSubmitManual"
                  :label="manualSubmitLabel"
                  @click="submitManualAction"
                />
                <q-btn
                  flat
                  round
                  icon="content_copy"
                  color="grey-8"
                  @click="copyManualPayload"
                >
                  <q-tooltip>复制请求参数</q-tooltip>
                </q-btn>
                <q-btn
                  flat
                  round
                  icon="delete_sweep"
                  color="grey-8"
                  @click="clearManualResult"
                >
                  <q-tooltip>清空烧录结果</q-tooltip>
                </q-btn>
              </div>
            </div>

            <div class="serial-settings-card manual-result-card">
              <div class="serial-settings-card__title">执行结果</div>
              <div
                class="status-line"
                :class="`status-line--${manualResultTone.state}`"
              >
                {{ manualStatusMessage }}
              </div>

              <q-linear-progress
                v-if="isSubmittingManual"
                indeterminate
                color="primary"
                class="execution-progress"
              />

              <div v-if="isSubmittingManual" class="execution-note">
                正在执行烧录。Vivado 与 J-Link 输出会实时显示在下方标签页中。
              </div>

              <div class="step-stack manual-step-stack">
                <article class="step-item">
                  <div class="step-item__head">
                    <strong>Bit</strong>
                    <q-icon
                      :name="stepIcon(manualStepBit)"
                      :color="stepColor(manualStepBit)"
                      size="20px"
                    />
                  </div>
                  <div class="step-item__body">
                    {{ stepMessage(manualStepBit, manualNeedsBit) }}
                  </div>
                </article>

                <article class="step-item">
                  <div class="step-item__head">
                    <strong>ELF</strong>
                    <q-icon
                      :name="stepIcon(manualStepElf)"
                      :color="stepColor(manualStepElf)"
                      size="20px"
                    />
                  </div>
                  <div class="step-item__body">
                    {{ stepMessage(manualStepElf, manualNeedsElf) }}
                  </div>
                </article>
              </div>

              <q-tabs
                v-model="manualActiveTab"
                dense
                active-color="primary"
                indicator-color="primary"
                no-caps
              >
                <q-tab name="stdout" label="Stdout" />
                <q-tab name="stderr" label="Stderr" />
                <q-tab name="json" label="JSON" />
              </q-tabs>

              <q-tab-panels v-model="manualActiveTab" animated class="log-tabs">
                <q-tab-panel name="stdout" class="log-tabs__panel">
                  <pre class="log-console manual-log-console">{{
                    manualStdoutText
                  }}</pre>
                </q-tab-panel>
                <q-tab-panel name="stderr" class="log-tabs__panel">
                  <pre
                    class="log-console log-console--error manual-log-console"
                    >{{ manualStderrText }}</pre
                  >
                </q-tab-panel>
                <q-tab-panel name="json" class="log-tabs__panel">
                  <pre class="log-console manual-log-console">{{
                    manualJsonText
                  }}</pre>
                </q-tab-panel>
              </q-tab-panels>
            </div>
          </div>
        </section>

        <section class="surface-block console-wide jlink-panel">
          <div class="block-head">
            <div>
              <h2 class="block-title">J-Link 复位控制</h2>
              <p class="serial-panel-caption">
                放在烧录和串口之间，便于完成烧录后快速复位，再继续串口调试。
              </p>
            </div>
          </div>

          <div class="jlink-control-actions">
            <q-btn
              v-for="action in jlinkActions"
              :key="action.value"
              color="primary"
              text-color="white"
              unelevated
              no-caps
              :icon="action.icon"
              :label="action.label"
              :loading="activeJlinkAction === action.value"
              :disable="isJlinkBusy"
              @click="runJlinkAction(action.value)"
            />
          </div>
          <div
            v-if="jlinkStatusMessage"
            class="jlink-control-status"
            :class="`jlink-control-status--${jlinkStatusTone}`"
          >
            {{ jlinkStatusMessage }}
          </div>
        </section>

        <section class="surface-block serial-output console-panel">
          <div class="block-head">
            <div>
              <h2 class="block-title">串口显示</h2>
              <p class="serial-panel-caption">
                接收数据显示在左侧，发送数据显示在右侧。
              </p>
            </div>
            <div class="serial-output-actions">
              <q-badge
                rounded
                color="grey-7"
                text-color="white"
                :label="`RX ${receivedBytes} B`"
              />
              <q-badge
                rounded
                color="blue-grey-7"
                text-color="white"
                :label="`TX ${sentBytes} B`"
              />
              <q-btn
                flat
                round
                :icon="autoScroll ? 'vertical_align_bottom' : 'pause'"
                color="grey-8"
                @click="autoScroll = !autoScroll"
              >
                <q-tooltip>{{
                  autoScroll ? "自动滚动已开启" : "自动滚动已暂停"
                }}</q-tooltip>
              </q-btn>
              <q-btn
                flat
                round
                icon="delete_sweep"
                color="grey-8"
                @click="clearLog"
              >
                <q-tooltip>清空记录</q-tooltip>
              </q-btn>
            </div>
          </div>

          <div ref="logElement" class="serial-chat-stream console-display">
            <div v-if="messages.length === 0" class="serial-chat-empty">
              串口打开后，接收数据会显示在左侧；发送成功的数据会显示在右侧。
            </div>

            <article
              v-for="message in messages"
              :key="message.id"
              class="serial-message"
              :class="`serial-message--${message.direction}`"
            >
              <div class="serial-message__meta">{{ message.meta }}</div>
              <div class="serial-message__bubble">
                {{ message.text || "(empty)" }}
              </div>
            </article>
          </div>
        </section>

        <section class="scope-debug-shell console-wide">
          <q-card flat bordered class="scope-status-bar">
            <div>
              <div class="scope-status-bar__title">示波器调试</div>
              <div class="scope-status-bar__subtitle">
                用于验证 SCPI 连接、通道配置和基础测量
              </div>
            </div>
            <div class="scope-status-bar__meta">
              <q-badge
                rounded
                :color="scopeConnectionBadgeColor"
                text-color="white"
                :label="scopeConnectionState"
              />
              <div class="scope-meta-line">
                <span>IDN</span>
                <strong>{{ scopeIdn || "未连接" }}</strong>
              </div>
              <div class="scope-meta-line">
                <span>最近操作</span>
                <strong>{{ scopeLastActionAt || "无" }}</strong>
              </div>
              <q-btn
                flat
                round
                icon="delete_sweep"
                color="grey-8"
                @click="clearScopeResult"
              >
                <q-tooltip>清空结果</q-tooltip>
              </q-btn>
            </div>
          </q-card>

          <div class="scope-debug-grid">
            <q-card flat bordered class="scope-task-panel">
              <q-card-section class="scope-card-section">
                <div class="serial-settings-card__title">连接配置</div>
                <div class="scope-form-grid">
                  <q-input
                    v-model="scopeForm.scope_ip"
                    outlined
                    dense
                    clearable
                    label="Scope IP"
                    :error="Boolean(scopeErrors.scope_ip)"
                    :error-message="scopeErrors.scope_ip"
                  />
                  <q-input
                    v-model.number="scopeForm.scope_port"
                    outlined
                    dense
                    type="number"
                    label="Port"
                    :error="Boolean(scopeErrors.scope_port)"
                    :error-message="scopeErrors.scope_port"
                  />
                  <q-input
                    v-model.number="scopeForm.timeout_ms"
                    outlined
                    dense
                    type="number"
                    label="Timeout(ms)"
                    :error="Boolean(scopeErrors.timeout_ms)"
                    :error-message="scopeErrors.timeout_ms"
                  />
                </div>
                <div class="scope-action-row">
                  <q-btn
                    color="primary"
                    text-color="white"
                    unelevated
                    no-caps
                    icon="cable"
                    label="检测连接"
                    :loading="activeScopeAction === 'scope_idn'"
                    :disable="isScopeBusy"
                    @click="detectScope"
                  />
                </div>
              </q-card-section>

              <q-separator />

              <q-card-section class="scope-card-section">
                <div class="serial-settings-card__title">通道配置</div>
                <div class="scope-form-grid">
                  <q-select
                    v-model="scopeForm.channel"
                    outlined
                    dense
                    emit-value
                    map-options
                    label="Channel"
                    :options="scopeChannelOptions"
                    :error="Boolean(scopeErrors.channel)"
                    :error-message="scopeErrors.channel"
                  />
                  <q-select
                    v-model="scopeForm.coupling"
                    outlined
                    dense
                    emit-value
                    map-options
                    label="Coupling"
                    :options="scopeCouplingOptions"
                  />
                  <q-input
                    v-model.number="scopeForm.scale"
                    outlined
                    dense
                    type="number"
                    label="Scale V/div"
                    :error="Boolean(scopeErrors.scale)"
                    :error-message="scopeErrors.scale"
                  />
                  <q-input
                    v-model.number="scopeForm.offset"
                    outlined
                    dense
                    type="number"
                    label="Offset V"
                  />
                </div>
                <div class="scope-action-row">
                  <q-btn
                    color="secondary"
                    text-color="white"
                    unelevated
                    no-caps
                    icon="tune"
                    label="应用通道配置"
                    :loading="activeScopeAction === 'scope_set_channel'"
                    :disable="isScopeBusy"
                    @click="applyScopeChannel"
                  />
                </div>
              </q-card-section>

              <q-separator />

              <q-card-section class="scope-card-section">
                <div class="serial-settings-card__title">测量配置</div>
                <div class="scope-form-grid">
                  <q-select
                    v-model="scopeForm.measure"
                    outlined
                    dense
                    emit-value
                    map-options
                    label="Measure Type"
                    :options="scopeMeasureOptions"
                  />
                  <q-input
                    v-model.number="scopeForm.expected_min"
                    outlined
                    dense
                    clearable
                    type="number"
                    label="Min"
                    :error="Boolean(scopeErrors.expected_range)"
                    :error-message="scopeErrors.expected_range"
                  />
                  <q-input
                    v-model.number="scopeForm.expected_max"
                    outlined
                    dense
                    clearable
                    type="number"
                    label="Max"
                    :error="Boolean(scopeErrors.expected_range)"
                  />
                  <q-input
                    :model-value="scopeMeasureUnit"
                    outlined
                    dense
                    readonly
                    label="Unit"
                  />
                </div>
                <div class="scope-action-row scope-action-row--split">
                  <q-btn
                    color="primary"
                    text-color="white"
                    unelevated
                    no-caps
                    icon="speed"
                    label="单次测量"
                    :loading="activeScopeAction === 'scope_measure'"
                    :disable="isScopeBusy"
                    @click="measureScopeOnce"
                  />
                  <q-btn
                    outline
                    color="primary"
                    no-caps
                    icon="data_object"
                    label="生成 TestStep JSON"
                    :disable="isScopeBusy"
                    @click="generateScopeTestStep"
                  />
                </div>
              </q-card-section>

              <q-separator />

              <q-card-section class="scope-card-section">
                <div class="serial-settings-card__title">波形读取</div>
                <div class="scope-form-grid">
                  <q-input
                    v-model.number="scopeForm.waveform_points"
                    outlined
                    dense
                    type="number"
                    label="Points"
                    :error="Boolean(scopeErrors.waveform_points)"
                    :error-message="scopeErrors.waveform_points"
                  />
                  <q-input
                    v-model.number="scopeForm.waveform_preview_points"
                    outlined
                    dense
                    type="number"
                    label="Preview Points"
                    :error="Boolean(scopeErrors.waveform_preview_points)"
                    :error-message="scopeErrors.waveform_preview_points"
                  />
                </div>
                <div class="scope-action-row">
                  <q-btn
                    color="primary"
                    text-color="white"
                    unelevated
                    no-caps
                    icon="timeline"
                    label="读取波形"
                    :loading="activeScopeAction === 'scope_waveform'"
                    :disable="isScopeBusy"
                    @click="readScopeWaveform"
                  />
                </div>
              </q-card-section>
            </q-card>

            <div class="scope-result-panel">
              <q-card flat bordered>
                <q-card-section class="scope-result-summary">
                  <div>
                    <div class="scope-result-summary__label">最近测量结果</div>
                    <div class="scope-result-value">
                      {{ scopeLatestValueText }}
                    </div>
                    <div class="scope-result-context">
                      {{ scopeLatestContext }}
                    </div>
                  </div>
                  <q-badge
                    rounded
                    :color="scopeLatestStatusColor"
                    text-color="white"
                    :label="scopeLatestStatusLabel"
                  />
                </q-card-section>
              </q-card>

              <q-card flat bordered>
                <q-card-section class="scope-card-section">
                  <div class="serial-settings-card__title">测量历史</div>
                  <q-table
                    flat
                    dense
                    hide-pagination
                    row-key="id"
                    :rows="scopeHistory"
                    :columns="scopeHistoryColumns"
                    :pagination="scopeHistoryPagination"
                    :rows-per-page-options="[MAX_SCOPE_HISTORY_COUNT]"
                    no-data-label="暂无示波器操作记录"
                  />
                </q-card-section>
              </q-card>

              <q-card flat bordered>
                <q-card-section class="scope-waveform-panel">
                  <div class="scope-waveform-head">
                    <div>
                      <div class="serial-settings-card__title">波形预览</div>
                      <p>{{ scopeWaveformSummary }}</p>
                    </div>
                    <q-badge
                      rounded
                      :color="
                        scopeWaveformPreview.length ? 'positive' : 'grey-7'
                      "
                      text-color="white"
                      :label="scopeWaveformPreview.length ? 'READY' : 'EMPTY'"
                    />
                  </div>

                  <div class="scope-waveform-chart">
                    <svg
                      v-if="scopeWaveformPath"
                      viewBox="0 0 640 180"
                      preserveAspectRatio="none"
                      role="img"
                    >
                      <line x1="0" y1="90" x2="640" y2="90" />
                      <polyline :points="scopeWaveformPath" />
                    </svg>
                    <div v-else class="scope-waveform-empty">
                      点击“读取波形”后，后端会读取当前通道波形并推送到这里。
                    </div>
                  </div>
                </q-card-section>
              </q-card>

              <q-card flat bordered>
                <q-expansion-item
                  default-opened
                  icon="receipt_long"
                  label="原始返回 / JSON"
                >
                  <q-card-section>
                    <pre class="log-console scope-result-console">{{
                      scopeRawPreview
                    }}</pre>
                  </q-card-section>
                </q-expansion-item>
              </q-card>
            </div>
          </div>
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
import { copyToClipboard, useQuasar } from "quasar";

type SerialFormat = "text" | "hex";
type SerialDirection = "rx" | "tx";
type ManualAction = "program_bit" | "program_elf" | "program_all";
type ManualLogTab = "stdout" | "stderr" | "json";
type SelectOption = { label: string; value: string };

type SerialPortItem = {
  device: string;
  description?: string | null;
};

type PortResponse = {
  items: SerialPortItem[];
};

type JLinkAction = "reset_run" | "reset_halt" | "resume";
type ScopeAction =
  | "scope_idn"
  | "scope_set_channel"
  | "scope_measure"
  | "scope_waveform"
  | "generate_test_step";

type DriverResult = {
  success: boolean;
  message?: string;
  stdout?: string;
  stderr?: string;
  data?: unknown;
};

type ManualResponse = DriverResult & {
  returncode?: number | null;
  data?: {
    bit_result?: DriverResult | null;
    elf_result?: DriverResult | null;
  } | null;
};

type ScopeConnectionState = "Idle" | "Connecting" | "Connected" | "Error";

type ScopeMeasure =
  | "vpp"
  | "vmax"
  | "vmin"
  | "vrms"
  | "vavg"
  | "freq"
  | "period"
  | "duty";

type ScopeMeasurementData = {
  channel?: string;
  measure?: string;
  value?: number;
  unit?: string;
  status?: string;
  raw?: string;
};

type ScopeWaveformData = {
  channel?: string;
  encoding?: string;
  format?: string;
  points?: number;
  preview_points?: number;
  preview?: number[];
  command?: string;
};

type ScopeHistoryRow = {
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

type SerialPayload = {
  hex?: string;
  text?: string;
  size?: number;
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
  timestamp?: number;
  data?: {
    payload?: SerialPayload;
  };
};

type ChatMessage = {
  id: number;
  direction: SerialDirection;
  meta: string;
  text: string;
  format: SerialFormat;
  size: number;
  timestamp: number;
};

const MAX_MESSAGE_COUNT = 400;
const MAX_MERGED_RX_CHARS = 16000;
const FLUSH_INTERVAL_MS = 80;
const CUSTOM_BAUDRATES_STORAGE_KEY = "serial-monitor-custom-baudrates";
const MAX_SCOPE_HISTORY_COUNT = 8;
const DEFAULT_BAUDRATES = [
  9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600
];
const ANSI_ESCAPE_PATTERN =
  /(?:\u001B\[[0-?]*[ -/]*[@-~]|\u001B\][^\u0007]*(?:\u0007|\u001B\\)|\u001B[@-_])/g;
const BACKSPACE_PATTERN = /[^\n]\u0008/g;

const jlinkActions: { label: string; value: JLinkAction; icon: string }[] = [
  { label: "复位运行", value: "reset_run", icon: "restart_alt" },
  { label: "复位停止", value: "reset_halt", icon: "stop_circle" },
  { label: "继续运行", value: "resume", icon: "play_arrow" }
];
const manualActionOptions = [
  { label: "Only Bit", value: "program_bit" },
  { label: "Only ELF", value: "program_elf" },
  { label: "Bit Then ELF", value: "program_all" }
];
const manualInterfaceOptions = [
  { label: "JTAG", value: "JTAG" },
  { label: "SWD", value: "SWD" }
];

const formatOptions = [
  { label: "文本", value: "text" },
  { label: "HEX", value: "hex" }
];

const bytesizeOptions = [5, 6, 7, 8].map(value => ({
  label: `${value} bit`,
  value
}));

const parityOptions = [
  { label: "无校验 (None)", value: "N" },
  { label: "奇校验 (Odd)", value: "O" },
  { label: "偶校验 (Even)", value: "E" },
  { label: "Mark", value: "M" },
  { label: "Space", value: "S" }
];

const stopbitsOptions = [
  { label: "1 bit", value: 1 },
  { label: "1.5 bit", value: 1.5 },
  { label: "2 bit", value: 2 }
];

const $q = useQuasar();

const form = reactive({
  port: "",
  baudrate: 115200,
  bytesize: 8,
  parity: "N",
  stopbits: 1,
  receiveFormat: "text" as SerialFormat,
  sendFormat: "text" as SerialFormat
});
const manualForm = reactive({
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

const customBaudrates = ref<number[]>([]);
const customBaudrate = ref<number | null>(null);
const ports = ref<SerialPortItem[]>([]);
const isLoadingPorts = ref(false);
const isOpening = ref(false);
const isClosing = ref(false);
const socketConnected = ref(false);
const uartConnected = ref(false);
const statusMessage = ref("Ready.");
const statusTone = ref<"idle" | "success" | "error">("idle");
const activeJlinkAction = ref<JLinkAction | null>(null);
const jlinkStatusMessage = ref("");
const jlinkStatusTone = ref<"idle" | "success" | "error">("idle");
const activeScopeAction = ref<ScopeAction | null>(null);
const scopeConnectionState = ref<ScopeConnectionState>("Idle");
const scopeIdn = ref("");
const scopeLastActionAt = ref("");
const scopeResult = ref<DriverResult | null>(null);
const scopeWaveformResult = ref<DriverResult | null>(null);
const scopeGeneratedTestStep = ref<Record<string, unknown> | null>(null);
const scopeHistory = ref<ScopeHistoryRow[]>([]);
const scopeErrors = reactive<Record<string, string>>({});
const sendText = ref("");
const appendNewline = ref(false);
const messages = ref<ChatMessage[]>([]);
const receivedBytes = ref(0);
const sentBytes = ref(0);
const autoScroll = ref(true);
const logElement = ref<HTMLElement | null>(null);
const isPageActive = ref(true);
const isSubmittingManual = ref(false);
const isCheckingManualHealth = ref(false);
const isLoadingFiles = ref(false);
const manualStatusMessage = ref(
  "Ready to execute a manual programming action."
);
const manualResponseView = ref<ManualResponse | null>(null);
const manualPendingPayload = ref<Record<string, unknown> | null>(null);
const manualActiveTab = ref<ManualLogTab>("stdout");
const manualStreamedStdout = ref("");
const manualStreamedStderr = ref("");
const manualStreamConnected = ref(false);
const bitOptions = ref<SelectOption[]>([]);
const elfOptions = ref<SelectOption[]>([]);
const filteredBitOptions = ref<SelectOption[]>([]);
const filteredElfOptions = ref<SelectOption[]>([]);
const isManualPageActive = ref(true);

let socket: WebSocket | null = null;
let flushTimer: number | null = null;
let reconnectTimer: number | null = null;
let messageId = 0;
const pendingMessages: ChatMessage[] = [];
let manualStreamSocket: WebSocket | null = null;
let manualReconnectTimer: number | null = null;

const baudrateOptions = computed(() =>
  [...new Set([...DEFAULT_BAUDRATES, ...customBaudrates.value])]
    .sort((left, right) => left - right)
    .map(value => ({
      label: String(value),
      value
    }))
);

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
const isJlinkBusy = computed(() => activeJlinkAction.value !== null);
const isScopeBusy = computed(() => activeScopeAction.value !== null);
const manualNeedsBit = computed(
  () =>
    manualForm.action === "program_bit" || manualForm.action === "program_all"
);
const manualNeedsElf = computed(
  () =>
    manualForm.action === "program_elf" || manualForm.action === "program_all"
);
const canSubmitManual = computed(() => {
  if (manualNeedsBit.value && !manualForm.bit_file.trim()) return false;
  if (manualNeedsElf.value && !manualForm.elf_file.trim()) return false;
  return true;
});
const manualResultTone = computed(() => {
  if (isSubmittingManual.value) {
    return { state: "running", color: "primary", label: "Running" };
  }
  if (!manualResponseView.value) {
    return { state: "idle", color: "grey-6", label: "Idle" };
  }
  if (manualResponseView.value.success) {
    return { state: "success", color: "positive", label: "Success" };
  }
  return { state: "error", color: "negative", label: "Failed" };
});
const manualSubmitLabel = computed(() =>
  isSubmittingManual.value ? "Executing..." : "Execute"
);
const manualStepBit = computed<DriverResult | null>(() => {
  if (!manualNeedsBit.value) return null;
  if (manualForm.action === "program_bit") return manualResponseView.value;
  return manualResponseView.value?.data?.bit_result ?? null;
});
const manualStepElf = computed<DriverResult | null>(() => {
  if (!manualNeedsElf.value) return null;
  if (manualForm.action === "program_elf") return manualResponseView.value;
  return manualResponseView.value?.data?.elf_result ?? null;
});
const manualStdoutText = computed(() => {
  if (manualStreamedStdout.value.trim())
    return manualStreamedStdout.value.trim();

  const chunks = [
    manualResponseView.value?.stdout,
    manualStepBit.value?.stdout,
    manualStepElf.value?.stdout
  ].filter(Boolean);
  if (!chunks.length && isSubmittingManual.value && !manualResponseView.value) {
    return "Request sent to /api/manual/execute.\nWaiting for backend response.";
  }
  return chunks.join("\n\n").trim() || "No stdout captured.";
});
const manualStderrText = computed(() => {
  if (manualStreamedStderr.value.trim())
    return manualStreamedStderr.value.trim();

  const chunks = [
    manualResponseView.value?.stderr,
    manualStepBit.value?.stderr,
    manualStepElf.value?.stderr
  ].filter(Boolean);
  return chunks.join("\n\n").trim() || "No stderr captured.";
});
const manualJsonText = computed(() => {
  if (manualResponseView.value) {
    return JSON.stringify(
      sanitizeFilePathsForDisplay(manualResponseView.value),
      null,
      2
    );
  }
  if (manualPendingPayload.value) {
    return JSON.stringify(
      {
        status: isSubmittingManual.value ? "running" : "pending",
        request: sanitizeFilePathsForDisplay(manualPendingPayload.value)
      },
      null,
      2
    );
  }
  return "{}";
});

const scopeForm = reactive({
  scope_ip: "192.168.31.28",
  scope_port: 5025 as number | null,
  timeout_ms: 5000,
  channel: "CH1",
  coupling: "DC",
  scale: 0.5,
  offset: 0,
  measure: "vpp" as ScopeMeasure,
  expected_min: null as number | null,
  expected_max: null as number | null,
  waveform_points: 1200,
  waveform_preview_points: 240
});

const scopeChannelOptions = ["CH1", "CH2", "CH3", "CH4"].map(value => ({
  label: value,
  value
}));

const scopeCouplingOptions = ["DC", "AC", "GND"].map(value => ({
  label: value,
  value
}));

const scopeMeasureOptions = [
  { label: "vpp，峰峰值", value: "vpp" },
  { label: "vmax，最大值", value: "vmax" },
  { label: "vmin，最小值", value: "vmin" },
  { label: "vrms，有效值", value: "vrms" },
  { label: "vavg，平均值", value: "vavg" },
  { label: "freq，频率", value: "freq" },
  { label: "period，周期", value: "period" },
  { label: "duty，占空比", value: "duty" }
];

const scopeHistoryColumns = [
  { name: "time", label: "time", field: "time", align: "left" as const },
  { name: "action", label: "action", field: "action", align: "left" as const },
  {
    name: "channel",
    label: "channel",
    field: "channel",
    align: "left" as const
  },
  {
    name: "measure",
    label: "measure",
    field: "measure",
    align: "left" as const
  },
  { name: "value", label: "value", field: "value", align: "right" as const },
  { name: "unit", label: "unit", field: "unit", align: "left" as const },
  { name: "status", label: "status", field: "status", align: "left" as const },
  {
    name: "message",
    label: "message",
    field: "message",
    align: "left" as const
  }
];

const scopeHistoryPagination = {
  rowsPerPage: MAX_SCOPE_HISTORY_COUNT
};

const scopeMeasureUnit = computed(() => {
  if (scopeForm.measure === "freq") return "Hz";
  if (scopeForm.measure === "period") return "s";
  if (scopeForm.measure === "duty") return "%";
  return "V";
});

const scopeConnectionBadgeColor = computed(() => {
  if (scopeConnectionState.value === "Connected") return "positive";
  if (scopeConnectionState.value === "Connecting") return "orange";
  if (scopeConnectionState.value === "Error") return "negative";
  return "grey-7";
});

const latestScopeMeasurement = computed(() => {
  const data = scopeResult.value?.data;
  if (!data || typeof data !== "object") return null;
  return data as ScopeMeasurementData;
});

const scopeLatestValueText = computed(() => {
  const measurement = latestScopeMeasurement.value;
  if (measurement?.value === undefined || measurement.value === null) {
    return "--";
  }
  return `${formatScopeValue(measurement.value)} ${measurement.unit || scopeMeasureUnit.value}`;
});

const scopeLatestContext = computed(() => {
  const measurement = latestScopeMeasurement.value;
  if (!measurement?.measure)
    return scopeResult.value?.message || "等待单次测量";
  return `${measurement.channel || scopeForm.channel} / ${measurement.measure} / ${scopeResult.value?.message || ""}`;
});

const scopeLatestStatusLabel = computed(() => {
  const status = latestScopeMeasurement.value?.status;
  if (status === "passed") return "PASS";
  if (status === "failed") return "FAIL";
  if (status === "error") return "ERROR";
  return "UNKNOWN";
});

const scopeLatestStatusColor = computed(() => {
  if (scopeLatestStatusLabel.value === "PASS") return "positive";
  if (scopeLatestStatusLabel.value === "FAIL") return "negative";
  if (scopeLatestStatusLabel.value === "ERROR") return "negative";
  return "grey-7";
});

const scopeRawPreview = computed(() => {
  return JSON.stringify(
    {
      backend: scopeResult.value,
      waveform: scopeWaveformResult.value,
      test_step: scopeGeneratedTestStep.value
    },
    null,
    2
  );
});

const scopeWaveformData = computed(() => {
  const data = scopeWaveformResult.value?.data;
  if (!data || typeof data !== "object") return null;
  return data as ScopeWaveformData;
});

const scopeWaveformPreview = computed(() => {
  return scopeWaveformData.value?.preview ?? [];
});

const scopeWaveformSummary = computed(() => {
  const data = scopeWaveformData.value;
  if (!data || !scopeWaveformPreview.value.length) {
    return "当前未读取波形。";
  }
  return `${data.channel || scopeForm.channel} / ${data.encoding || "-"} / ${data.preview_points || scopeWaveformPreview.value.length} of ${data.points || 0} points`;
});

const scopeWaveformPath = computed(() => {
  const values = scopeWaveformPreview.value;
  if (values.length < 2) return "";

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 640;
      const y = 170 - ((value - min) / span) * 160;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
});

function sanitizedManualPayload() {
  return Object.fromEntries(
    Object.entries(manualForm).filter(
      ([, value]) => value !== "" && value !== null
    )
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
      !bitOptions.value.some(option => option.value === manualForm.bit_file)
    ) {
      manualForm.bit_file = firstBitOption.value;
    }

    const firstElfOption = elfOptions.value[0];
    if (
      firstElfOption &&
      !elfOptions.value.some(option => option.value === manualForm.elf_file)
    ) {
      manualForm.elf_file = firstElfOption.value;
    }
  } catch (error) {
    manualStatusMessage.value =
      error instanceof Error ? error.message : "Unable to load file list.";
  } finally {
    isLoadingFiles.value = false;
  }
}

function manualWebsocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/ws/terminal`;
}

function clearManualReconnectTimer() {
  if (manualReconnectTimer !== null) {
    window.clearTimeout(manualReconnectTimer);
    manualReconnectTimer = null;
  }
}

function appendManualStreamChunk(target: "stdout" | "stderr", chunk: string) {
  if (!chunk.trim()) return;

  if (target === "stderr") {
    manualStreamedStderr.value = `${manualStreamedStderr.value}${chunk}`;
    if (isSubmittingManual.value) manualActiveTab.value = "stderr";
    return;
  }

  manualStreamedStdout.value = `${manualStreamedStdout.value}${chunk}`;
}

function sanitizeTerminalChunk(chunk: string) {
  let normalized = chunk.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  normalized = normalized.replace(ANSI_ESCAPE_PATTERN, "");

  while (BACKSPACE_PATTERN.test(normalized)) {
    normalized = normalized.replace(BACKSPACE_PATTERN, "");
  }

  return normalized.replace(/\u0000/g, "");
}

function handleManualStreamMessage(rawMessage: string) {
  if (!rawMessage) return;
  if (rawMessage.startsWith("Connected to backend shell:")) return;

  const normalized = sanitizeTerminalChunk(rawMessage);
  if (normalized.includes("success=") && normalized.includes("message:"))
    return;

  for (const line of normalized.split("\n")) {
    if (!line.trim()) continue;
    if (line.startsWith("[stderr] ")) {
      appendManualStreamChunk("stderr", `${line.slice(9)}\n`);
      continue;
    }
    appendManualStreamChunk("stdout", `${line}\n`);
  }
}

function scheduleManualReconnect() {
  if (!isManualPageActive.value || manualReconnectTimer !== null) return;
  manualReconnectTimer = window.setTimeout(() => {
    manualReconnectTimer = null;
    connectManualStreamSocket();
  }, 1500);
}

function connectManualStreamSocket() {
  if (
    manualStreamSocket &&
    (manualStreamSocket.readyState === WebSocket.OPEN ||
      manualStreamSocket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  manualStreamSocket = new WebSocket(manualWebsocketUrl());

  manualStreamSocket.onopen = () => {
    manualStreamConnected.value = true;
    clearManualReconnectTimer();
  };

  manualStreamSocket.onmessage = event => {
    handleManualStreamMessage(String(event.data));
  };

  manualStreamSocket.onerror = () => {
    manualStreamConnected.value = false;
  };

  manualStreamSocket.onclose = () => {
    manualStreamConnected.value = false;
    manualStreamSocket = null;
    scheduleManualReconnect();
  };
}

function disconnectManualStreamSocket() {
  clearManualReconnectTimer();
  manualStreamConnected.value = false;
  if (manualStreamSocket) {
    manualStreamSocket.close();
    manualStreamSocket = null;
  }
}

async function checkManualHealth() {
  isCheckingManualHealth.value = true;
  try {
    const response = await fetch("/api/health");
    const data = (await response.json()) as { status?: string };
    manualStatusMessage.value = response.ok
      ? `Backend is ${data.status ?? "ok"}.`
      : "Backend health check failed.";
  } catch (error) {
    manualStatusMessage.value =
      error instanceof Error ? error.message : "Unable to reach backend.";
  } finally {
    isCheckingManualHealth.value = false;
  }
}

async function submitManualAction() {
  isSubmittingManual.value = true;
  manualStatusMessage.value = "Executing manual programming action...";
  manualResponseView.value = null;
  manualPendingPayload.value = sanitizedManualPayload();
  manualStreamedStdout.value = "";
  manualStreamedStderr.value = "";
  manualActiveTab.value = "stdout";

  try {
    const response = await fetch("/api/manual/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(manualPendingPayload.value)
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
    manualResponseView.value = data;
    manualStatusMessage.value =
      data.message ||
      (data.success ? "Execution completed." : "Execution failed.");
    manualActiveTab.value = data.success
      ? "stdout"
      : data.stderr
        ? "stderr"
        : "json";
  } catch (error) {
    manualResponseView.value = {
      success: false,
      message: "Network request failed",
      data: null,
      stdout: "",
      stderr: error instanceof Error ? error.message : "Unknown request error",
      returncode: null
    };
    manualStatusMessage.value =
      "Manual programming request failed before reaching backend.";
    manualActiveTab.value = "stderr";
  } finally {
    isSubmittingManual.value = false;
  }
}

async function copyManualPayload() {
  await copyToClipboard(JSON.stringify(sanitizedManualPayload(), null, 2));
  $q.notify({ type: "positive", message: "Payload copied." });
}

function clearManualResult() {
  manualResponseView.value = null;
  manualPendingPayload.value = null;
  manualStreamedStdout.value = "";
  manualStreamedStderr.value = "";
  manualStatusMessage.value = "Result cleared.";
  manualActiveTab.value = "stdout";
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
    if (message.state === "ready") {
      isOpening.value = false;
      isClosing.value = false;
      setStatus("UART monitor ready.", "idle");
      return;
    }
    if (message.state === "closed") {
      isOpening.value = false;
      isClosing.value = false;
      uartConnected.value = false;
      if (statusTone.value !== "error") {
        setStatus("UART closed.", "idle");
      }
      return;
    }
    setStatus(`State: ${message.state ?? "unknown"}.`, "idle");
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
    if (
      ["open", "read", "write"].includes(message.action ?? "") &&
      !message.success
    ) {
      isOpening.value = false;
      isClosing.value = false;
      uartConnected.value = false;
    }
    if (message.action === "write" && message.success) {
      const outgoing = createOutgoingMessage(message);
      if (outgoing) {
        sentBytes.value += message.data?.payload?.size ?? 0;
        pendingMessages.push(outgoing);
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
    uartConnected.value = false;
    setStatus(message.message || "UART error.", "error");
    return;
  }

  if (message.type === "data") {
    receivedBytes.value += message.size ?? 0;
    pendingMessages.push(createIncomingMessage(message));
  }
}

function createIncomingMessage(message: UartMessage): ChatMessage {
  const timestamp = message.timestamp ?? Date.now() / 1000;
  const content =
    form.receiveFormat === "hex" ? (message.hex ?? "") : (message.text ?? "");
  const size = message.size ?? 0;

  return {
    id: nextMessageId(),
    direction: "rx",
    meta: buildMeta("接收", form.receiveFormat, size, timestamp),
    text: content,
    format: form.receiveFormat,
    size,
    timestamp
  };
}

function createOutgoingMessage(message: UartMessage): ChatMessage | null {
  const payload = message.data?.payload;
  if (!payload) return null;

  const content =
    form.sendFormat === "hex" ? (payload.hex ?? "") : (payload.text ?? "");
  const size = payload.size ?? 0;
  const timestamp = message.timestamp ?? Date.now() / 1000;

  return {
    id: nextMessageId(),
    direction: "tx",
    meta: buildMeta("发送", form.sendFormat, size, timestamp),
    text: content,
    format: form.sendFormat,
    size,
    timestamp
  };
}

function nextMessageId() {
  messageId += 1;
  return messageId;
}

function buildMeta(
  label: string,
  format: SerialFormat,
  size: number,
  timestamp: number
) {
  return `${label} · ${format.toUpperCase()} · ${size} B · ${formatTime(timestamp)}`;
}

function formatTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function setStatus(message: string, tone: "idle" | "success" | "error") {
  statusMessage.value = message;
  statusTone.value = tone;
}

function flushMessages() {
  if (!pendingMessages.length) return;

  const nextItems = [...messages.value];
  for (const pending of pendingMessages) {
    appendChatMessage(nextItems, pending);
  }
  pendingMessages.length = 0;
  messages.value =
    nextItems.length > MAX_MESSAGE_COUNT
      ? nextItems.slice(-MAX_MESSAGE_COUNT)
      : nextItems;

  if (autoScroll.value) {
    void nextTick(() => {
      if (logElement.value) {
        logElement.value.scrollTop = logElement.value.scrollHeight;
      }
    });
  }
}

function appendChatMessage(items: ChatMessage[], nextMessage: ChatMessage) {
  const lastMessage = items[items.length - 1];
  if (!lastMessage || !shouldMergeMessage(lastMessage, nextMessage)) {
    items.push(nextMessage);
    return;
  }

  lastMessage.text += nextMessage.text;
  lastMessage.size += nextMessage.size;
  lastMessage.timestamp = nextMessage.timestamp;
  lastMessage.meta = buildMeta(
    "接收",
    lastMessage.format,
    lastMessage.size,
    lastMessage.timestamp
  );
}

function shouldMergeMessage(
  lastMessage: ChatMessage | undefined,
  nextMessage: ChatMessage
) {
  if (!lastMessage) return false;
  if (lastMessage.direction !== "rx" || nextMessage.direction !== "rx") {
    return false;
  }
  if (lastMessage.format !== nextMessage.format) return false;
  return (
    lastMessage.text.length + nextMessage.text.length <= MAX_MERGED_RX_CHARS
  );
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
  uartConnected.value = false;
  setStatus("Opening UART...", "idle");
  const sent = sendSocket({
    type: "open",
    port: form.port,
    baudrate: form.baudrate,
    bytesize: form.bytesize,
    parity: form.parity,
    stopbits: form.stopbits
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
  if (!canSend.value) {
    setStatus("UART is not connected.", "error");
    uartConnected.value = false;
    return;
  }
  sendSocket({
    type: "write",
    data: sendText.value,
    format: form.sendFormat,
    append_newline: appendNewline.value
  });
}

async function runJlinkAction(action: JLinkAction) {
  activeJlinkAction.value = action;
  jlinkStatusMessage.value = `${jlinkActions.find(item => item.value === action)?.label ?? "J-Link 操作"}中...`;
  jlinkStatusTone.value = "idle";

  try {
    const response = await fetch("/api/jlink/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action })
    });
    const result = (await response.json()) as DriverResult;

    if (!response.ok || !result.success) {
      const detail =
        result.stderr?.trim() || result.message || `HTTP ${response.status}`;
      throw new Error(detail);
    }

    jlinkStatusMessage.value =
      result.stdout?.trim() || result.message || "J-Link 操作完成。";
    jlinkStatusTone.value = "success";
  } catch (error) {
    jlinkStatusMessage.value =
      error instanceof Error ? error.message : "J-Link 操作失败。";
    jlinkStatusTone.value = "error";
  } finally {
    activeJlinkAction.value = null;
  }
}

async function detectScope() {
  if (!validateScopeForm("connection")) return;

  activeScopeAction.value = "scope_idn";
  scopeConnectionState.value = "Connecting";

  try {
    const result = await postScope<DriverResult>(
      "/api/scope/idn",
      scopeBasePayload()
    );
    scopeResult.value = result;
    assertScopeSuccess(result);
    const data = result.data as { idn?: string } | null;
    scopeIdn.value = data?.idn || result.stdout?.trim() || "";
    scopeConnectionState.value = "Connected";
    recordScopeHistory("scope_idn", result);
    notifyScope("positive", "示波器连接成功。");
  } catch (error) {
    scopeConnectionState.value = "Error";
    handleScopeError(error, "示波器连接失败。", "scope_idn");
  } finally {
    activeScopeAction.value = null;
    touchScopeActionTime();
  }
}

async function applyScopeChannel() {
  if (!validateScopeForm("channel")) return;

  activeScopeAction.value = "scope_set_channel";

  try {
    const result = await postScope<DriverResult>("/api/scope/channel", {
      ...scopeBasePayload(),
      channel: scopeForm.channel,
      enabled: true,
      scale: Number(scopeForm.scale),
      offset: Number(scopeForm.offset || 0),
      coupling: scopeForm.coupling
    });
    scopeResult.value = result;
    assertScopeSuccess(result);
    recordScopeHistory("scope_set_channel", result);
    notifyScope("positive", "通道配置已应用。");
  } catch (error) {
    scopeConnectionState.value = "Error";
    handleScopeError(error, "通道配置失败。", "scope_set_channel");
  } finally {
    activeScopeAction.value = null;
    touchScopeActionTime();
  }
}

async function measureScopeOnce() {
  if (!validateScopeForm("measure")) return;

  activeScopeAction.value = "scope_measure";

  try {
    const result = await postScope<DriverResult>("/api/scope/measure", {
      ...scopeBasePayload(),
      channel: scopeForm.channel,
      measure: scopeForm.measure,
      expected: scopeExpectedPayload()
    });
    scopeResult.value = result;
    assertScopeSuccess(result);
    recordScopeHistory("scope_measure", result);
    notifyScope("positive", "单次测量完成。");
  } catch (error) {
    scopeConnectionState.value = "Error";
    handleScopeError(error, "单次测量失败。", "scope_measure");
  } finally {
    activeScopeAction.value = null;
    touchScopeActionTime();
  }
}

async function readScopeWaveform() {
  if (!validateScopeForm("waveform")) return;

  activeScopeAction.value = "scope_waveform";

  try {
    const result = await postScope<DriverResult>("/api/scope/waveform", {
      ...scopeBasePayload(),
      channel: scopeForm.channel,
      points: Number(scopeForm.waveform_points),
      preview_points: Number(scopeForm.waveform_preview_points),
      waveform_format: "BYTE",
      binary: true,
      datatype: "B"
    });
    scopeWaveformResult.value = result;
    scopeResult.value = result;
    assertScopeSuccess(result);
    recordScopeHistory("scope_waveform", result);
    notifyScope("positive", "波形读取完成。");
  } catch (error) {
    scopeConnectionState.value = "Error";
    handleScopeError(error, "波形读取失败。", "scope_waveform");
  } finally {
    activeScopeAction.value = null;
    touchScopeActionTime();
  }
}

function generateScopeTestStep() {
  if (!validateScopeForm("measure")) return;

  activeScopeAction.value = "generate_test_step";
  const expected: Record<string, unknown> = { unit: scopeMeasureUnit.value };
  if (scopeForm.expected_min !== null && scopeForm.expected_min !== undefined) {
    expected.min = Number(scopeForm.expected_min);
  }
  if (scopeForm.expected_max !== null && scopeForm.expected_max !== undefined) {
    expected.max = Number(scopeForm.expected_max);
  }

  scopeGeneratedTestStep.value = {
    step_type: "scope_measure",
    name: `测量 ${scopeForm.channel} ${scopeForm.measure}`,
    config_json: {
      channel: scopeForm.channel,
      measure: scopeForm.measure
    },
    expected_json: expected,
    timeout_ms: Number(scopeForm.timeout_ms)
  };
  recordScopeHistory("generate_test_step", {
    success: true,
    message: "TestStep JSON generated",
    data: scopeGeneratedTestStep.value
  });
  notifyScope("positive", "TestStep JSON 已生成。");
  activeScopeAction.value = null;
  touchScopeActionTime();
}

async function postScope<T>(url: string, payload: Record<string, unknown>) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const result = (await response.json()) as T;
  if (!response.ok) {
    const detail = result as DriverResult;
    throw new Error(
      detail.stderr?.trim() || detail.message || `HTTP ${response.status}`
    );
  }
  return result;
}

function assertScopeSuccess(result: DriverResult) {
  if (result.success) return;
  throw new Error(
    result.stderr?.trim() || result.message || "Scope 操作失败。"
  );
}

function scopeBasePayload() {
  return {
    ip: scopeForm.scope_ip,
    port: Number(scopeForm.scope_port),
    timeout_ms: Number(scopeForm.timeout_ms)
  };
}

function scopeExpectedPayload() {
  const expected: Record<string, number> = {};
  if (scopeForm.expected_min !== null && scopeForm.expected_min !== undefined) {
    expected.min = Number(scopeForm.expected_min);
  }
  if (scopeForm.expected_max !== null && scopeForm.expected_max !== undefined) {
    expected.max = Number(scopeForm.expected_max);
  }
  return Object.keys(expected).length > 0 ? expected : undefined;
}

function validateScopeForm(
  mode: "connection" | "channel" | "measure" | "waveform"
) {
  Object.keys(scopeErrors).forEach(key => {
    delete scopeErrors[key];
  });

  if (!scopeForm.scope_ip.trim()) scopeErrors.scope_ip = "IP 不能为空";
  if (!Number.isFinite(Number(scopeForm.scope_port))) {
    scopeErrors.scope_port = "Port 必须是数字";
  }
  if (
    !Number.isFinite(Number(scopeForm.timeout_ms)) ||
    Number(scopeForm.timeout_ms) <= 0
  ) {
    scopeErrors.timeout_ms = "Timeout 必须大于 0";
  }

  if (mode === "channel" || mode === "measure" || mode === "waveform") {
    if (!["CH1", "CH2", "CH3", "CH4"].includes(scopeForm.channel)) {
      scopeErrors.channel = "Channel 必须是 CH1 到 CH4";
    }
    if (
      !Number.isFinite(Number(scopeForm.scale)) ||
      Number(scopeForm.scale) <= 0
    ) {
      scopeErrors.scale = "Scale 必须大于 0";
    }
  }

  if (mode === "waveform") {
    if (
      !Number.isFinite(Number(scopeForm.waveform_points)) ||
      Number(scopeForm.waveform_points) <= 0
    ) {
      scopeErrors.waveform_points = "Points 必须大于 0";
    }
    if (
      !Number.isFinite(Number(scopeForm.waveform_preview_points)) ||
      Number(scopeForm.waveform_preview_points) <= 0
    ) {
      scopeErrors.waveform_preview_points = "Preview Points 必须大于 0";
    }
  }

  const minValue = scopeForm.expected_min;
  const maxValue = scopeForm.expected_max;
  if (
    minValue !== null &&
    maxValue !== null &&
    minValue !== undefined &&
    maxValue !== undefined &&
    Number(minValue) > Number(maxValue)
  ) {
    scopeErrors.expected_range = "Min 不能大于 Max";
  }

  const valid = Object.keys(scopeErrors).length === 0;
  if (!valid) notifyScope("negative", "请先修正示波器配置。");
  return valid;
}

function handleScopeError(error: unknown, fallback: string, action: string) {
  const message = error instanceof Error ? error.message : fallback;
  scopeResult.value = {
    success: false,
    message,
    stderr: message
  };
  recordScopeHistory(action, scopeResult.value);
  notifyScope("negative", message);
}

function recordScopeHistory(action: string, result: DriverResult) {
  const data =
    result.data && typeof result.data === "object"
      ? (result.data as ScopeMeasurementData)
      : {};
  const row: ScopeHistoryRow = {
    id: Date.now(),
    time: new Date().toLocaleTimeString(),
    action,
    channel: data.channel || scopeForm.channel || "-",
    measure: data.measure || scopeForm.measure || "-",
    value: data.value === undefined ? "-" : formatScopeValue(data.value),
    unit: data.unit || scopeMeasureUnit.value || "-",
    status: data.status || (result.success ? "ok" : "error"),
    message: result.message || result.stderr || "-"
  };
  scopeHistory.value = [row, ...scopeHistory.value].slice(
    0,
    MAX_SCOPE_HISTORY_COUNT
  );
}

function notifyScope(type: "positive" | "negative", message: string) {
  if (typeof $q.notify === "function") {
    $q.notify({ type, message, timeout: 1800 });
  }
}

function touchScopeActionTime() {
  scopeLastActionAt.value = new Date().toLocaleString();
}

function formatScopeValue(value: number) {
  if (!Number.isFinite(Number(value))) return String(value);
  return Number(value)
    .toPrecision(6)
    .replace(/\.?0+$/, "");
}

function clearLog() {
  pendingMessages.length = 0;
  messages.value = [];
  receivedBytes.value = 0;
  sentBytes.value = 0;
}

function clearScopeResult() {
  scopeResult.value = null;
  scopeWaveformResult.value = null;
  scopeGeneratedTestStep.value = null;
  scopeHistory.value = [];
  scopeConnectionState.value = scopeIdn.value ? "Connected" : "Idle";
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
  connectManualStreamSocket();
  void loadPorts();
  void loadFileOptions();
  flushTimer = window.setInterval(flushMessages, FLUSH_INTERVAL_MS);
});

onBeforeUnmount(() => {
  isPageActive.value = false;
  isManualPageActive.value = false;
  clearReconnectTimer();
  disconnectManualStreamSocket();
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
