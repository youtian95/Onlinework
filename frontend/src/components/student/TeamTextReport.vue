<!-- 分组文字报告模块：输入题目、小组、认领区域、个人报告和登录凭证；学生仅编辑本人区域，其他区域及管理端只读。草稿按学生和区域隔离，不判题计分。 -->
<template>
  <section class="text-report">
    <h2>文字报告</h2>
    <p>{{ readOnly ? '此区域仅供查看，只有认领该区域的组员可以填写和提交。' : '请填写本人认领区域的报告。回车用于换行，填写完成后点击“提交报告”。' }}</p>
    <label :for="textareaId">报告内容</label>
    <textarea :id="textareaId" v-model="draft" rows="22" maxlength="100000" :readonly="readOnly || disabled || saving" placeholder="请填写所选项目、分析思路、设计计算、结论和小组分工……"></textarea>
    <div class="report-meta">
      <span>{{ draft.length }} / 100000 字符</span>
      <span v-if="saved.updated_at">最近提交：{{ formatTime(saved.updated_at) }}，提交者：{{ saved.student_id }}</span>
      <span v-else>该区域尚未提交报告</span>
    </div>
    <div v-if="!readOnly" class="report-actions">
      <button v-if="!readOnly" type="button" :disabled="disabled || saving || !draft.trim()" @click="submitReport">{{ saving ? '提交中……' : '提交报告' }}</button>
    </div>
    <p v-if="message" role="status" :class="{ error: hasError }">{{ message }}</p>
    <p v-else-if="!readOnly && draft !== saved.content" class="draft-hint">当前文字尚未提交，草稿已暂存在本机浏览器。</p>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import axios from 'axios'

// problemId：题目编号；teamId：小组编号；subproblemNo：认领区域；submission：个人报告；token：登录凭证；disabled：截止状态；readOnly：非本人区域或管理端只读。
const props = defineProps({ problemId: { type: String, required: true }, teamId: { type: Number, default: null }, subproblemNo: { type: Number, required: true }, submission: { type: Object, default: () => ({}) }, token: { type: String, default: '' }, disabled: { type: Boolean, default: false }, readOnly: { type: Boolean, default: false } })
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const draft = ref('')
const saved = ref({ content: '', revision: 0 })
const revision = ref(0)
const saving = ref(false)
const message = ref('')
const hasError = ref(false)
const textareaId = computed(() => `team-text-${props.teamId ?? 'preview'}-${props.subproblemNo}`)
const draftKey = computed(() => `team-text-draft:${localStorage.getItem('studentId') || ''}:${props.problemId}:${props.teamId}:${props.subproblemNo}`)
// 生成当前学生的提交鉴权配置。
const authConfig = () => ({ headers: { Authorization: `Bearer ${props.token}` } })

// report：服务器上的完整报告；初始化文字和版本，不将旧版本草稿伪装为最新报告。
const applyReport = (report) => {
  saved.value = report || { content: '', revision: 0 }
  draft.value = saved.value.content || ''
  revision.value = saved.value.revision || 0
  message.value = ''
}

watch(() => [props.teamId, props.subproblemNo, props.submission, props.readOnly], () => {
  applyReport(props.submission)
  if (props.readOnly) return
  try {
    const cached = JSON.parse(localStorage.getItem(draftKey.value) || 'null')
    if (cached) {
      draft.value = cached.content
      revision.value = cached.revision
    }
  } catch {
    // 本机存储不可用时仍可编辑和提交。
  }
}, { immediate: true })

watch(draft, () => {
  if (props.readOnly) return
  try {
    if (draft.value === saved.value.content) localStorage.removeItem(draftKey.value)
    else localStorage.setItem(draftKey.value, JSON.stringify({ content: draft.value, revision: revision.value }))
  } catch {
    // 草稿缓存失败不影响服务端提交。
  }
})

// 点击提交才保存本人报告；保留换行，版本冲突时保留本机文字。
const submitReport = async () => {
  saving.value = true
  message.value = ''
  try {
    const result = await axios.put(`${API_BASE_URL}/problems/${encodeURIComponent(props.problemId)}/team/text`, { subproblem_no: props.subproblemNo, content: draft.value, revision: revision.value }, authConfig())
    applyReport(result.data.text_submission)
    localStorage.removeItem(draftKey.value)
    hasError.value = false
    message.value = '本区域报告已提交，其他组员的内容不受影响。不进行批改或计分。'
  } catch (error) {
    hasError.value = true
    message.value = error.response?.data?.detail || '提交失败，当前文字已保留，请稍后重试。'
  } finally {
    saving.value = false
  }
}

// iso：服务端 UTC 时间；输出本地可读的最近提交时间。
const formatTime = (iso) => new Date(/Z$|[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`).toLocaleString()

</script>

<style scoped>
.text-report { padding: 24px; border: 1px solid #dbe4f0; border-radius: 18px; background: #fff; margin-top: 20px; }
h2 { margin-top: 0; }
p { color: #475569; line-height: 1.7; }
label { display: block; font-weight: 700; margin-bottom: 10px; }
textarea { box-sizing: border-box; width: 100%; min-height: 480px; padding: 16px; border: 1px solid #94a3b8; border-radius: 10px; font: inherit; line-height: 1.9; resize: vertical; }
textarea:focus { outline: 2px solid #93c5fd; border-color: #2563eb; }
textarea[readonly] { background: #f8fafc; }
.report-meta, .report-actions { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; margin-top: 14px; }
.report-meta { color: #64748b; font-size: 13px; }
.report-actions { justify-content: flex-start; }
button { border: 0; border-radius: 8px; padding: 12px 20px; background: #2563eb; color: #fff; font: inherit; cursor: pointer; }
button:disabled { opacity: .55; cursor: not-allowed; }
.error { color: #b91c1c; }
.draft-hint { color: #92400e; }
</style>
