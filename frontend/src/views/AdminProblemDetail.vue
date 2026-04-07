<template>
  <div class="admin-problem-detail-page">
    <header class="page-header">
      <div class="header-left">
        <button type="button" class="back-btn" @click="goBack">← 返回题目管理</button>
        <div>
          <h1>{{ problemTitle }}</h1>
          <p class="problem-id">题目 ID: {{ problemId }}</p>
        </div>
      </div>
      <div class="state-badges">
        <span class="badge" :class="state.is_visible ? 'ok' : 'warn'">
          {{ state.is_visible ? '已发布' : '未发布' }}
        </span>
        <span class="badge" :class="state.is_deleted ? 'danger' : 'ok'">
          {{ state.is_deleted ? '已删除' : '正常' }}
        </span>
        <span class="badge" :class="state.is_public_view ? 'ok' : 'neutral'">
          {{ state.is_public_view ? '游客可见' : '游客不可见' }}
        </span>
      </div>
    </header>

    <div v-if="loading" class="loading-state">加载中...</div>
    <div v-else-if="error" class="error-state">{{ error }}</div>
    <div v-else class="content-layout">
      <section ref="contentCardRef" class="card content-card">
        <div class="card-title-row">
          <div class="content-meta">
            <span v-if="state.deadline" class="deadline-text">截止: {{ formatTime(state.deadline) }}</span>
            <span class="viewer-tag">{{ viewerText }}</span>
          </div>
        </div>

        <div :key="contentViewKey">
          <template v-if="renderSequence.length">
            <template v-for="segment in renderSequence" :key="segment.key">
              <div
                v-if="segment.type === 'plain'"
                class="markdown-body problem-content"
                v-html="segment.html"
              ></div>

              <article
                v-else-if="segment.type === 'subproblem' && subproblemMap[segment.subproblem_no]"
                class="subproblem-card"
              >
                <div class="subproblem-header">
                  <strong>子题 {{ segment.subproblem_no }}</strong>
                </div>
                <div class="markdown-body" v-html="subproblemMap[segment.subproblem_no].html"></div>
              </article>
            </template>
          </template>

          <template v-else>
            <div class="markdown-body problem-content" v-html="renderedContent"></div>
            <article
              v-for="block in renderedSubproblems"
              :key="block.subproblem_no"
              class="subproblem-card"
            >
              <div class="subproblem-header">
                <strong>子题 {{ block.subproblem_no }}</strong>
              </div>
              <div class="markdown-body" v-html="block.html"></div>
            </article>
          </template>
        </div>
      </section>

      <AdminProblemRankingPanel
        :teamwork-enabled="teamworkEnabled"
        :teamwork-config="teamworkConfig"
        :team-rows="teamRows"
        :selected-team-id="selectedTeamId"
        :selected-team="selectedTeam"
        :ranking-rows="rankingRows"
        :student-options="studentOptions"
        :selected-student-id="selectedStudentId"
        :selected-student-rank="selectedStudentRank"
        :progress-text="progressText"
        :progress-class="progressClass"
        :format-time="formatTime"
        :saving-team-config="savingTeamConfig"
        @update:selected-team-id="onTeamChange"
        @update:selected-student-id="onStudentChange"
        @save:team-count="saveTeamCount"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { marked } from 'marked'
import markedKatex from 'marked-katex-extension'
import AdminProblemRankingPanel from '../components/admin/AdminProblemRankingPanel.vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

marked.use(markedKatex({ throwOnError: false, trust: true, strict: 'ignore' }))

const route = useRoute()
const router = useRouter()
const adminToken = localStorage.getItem('adminToken') || ''

const loading = ref(true)
const error = ref('')
const contentCardRef = ref(null)

const problemTitle = ref('')
const state = ref({
  is_visible: false,
  is_deleted: false,
  is_public_view: false,
  deadline: null,
})

const renderedContent = ref('')
const renderedSubproblems = ref([])
const renderSequence = ref([])
const attemptStatus = ref({})
const inputMeta = ref({})

const teamworkConfig = ref(null)
const teams = ref([])
const teamRankingMap = ref({})
const rankingRows = ref([])
const studentOptions = ref([])
const savingTeamConfig = ref(false)

const selectedTeamId = ref(null)
const selectedStudentId = ref('')
const contentVersion = ref(0)

const problemId = computed(() => String(route.params.id || ''))
const teamworkEnabled = computed(() => !!teamworkConfig.value)

const subproblemMap = computed(() => {
  const mapping = {}
  for (const block of renderedSubproblems.value) {
    mapping[block.subproblem_no] = block
  }
  return mapping
})

const studentNameMap = computed(() => {
  const mapping = {}
  for (const student of studentOptions.value) {
    mapping[student.student_id] = student.name || student.student_id
  }
  return mapping
})

const selectedStudentRank = computed(() => {
  if (!selectedStudentId.value) return null
  return rankingRows.value.find((item) => item.student_id === selectedStudentId.value) || null
})

const selectedTeam = computed(() => {
  return teamRows.value.find((item) => item.team_id === selectedTeamId.value) || null
})

const teamRows = computed(() => {
  return (teams.value || [])
    .map((team) => {
      const ranking = teamRankingMap.value[team.team_id] || {}
      return {
        ...team,
        rank: ranking.rank ?? null,
        score: ranking.score ?? 0,
        total_possible: ranking.total_possible ?? 0,
        score_rate: ranking.score_rate ?? 0,
        last_update: ranking.last_update || null,
      }
    })
    .sort((a, b) => {
      const rankA = Number.isFinite(Number(a.rank)) ? Number(a.rank) : Number.MAX_SAFE_INTEGER
      const rankB = Number.isFinite(Number(b.rank)) ? Number(b.rank) : Number.MAX_SAFE_INTEGER
      if (rankA !== rankB) {
        return rankA - rankB
      }
      return a.team_no - b.team_no
    })
})

const viewerText = computed(() => {
  if (teamworkEnabled.value) {
    if (!selectedTeam.value) return '当前查看: 全局题面'
    return `当前查看: ${selectedTeam.value.name || `第${selectedTeam.value.team_no}队`}`
  }
  if (!selectedStudentId.value) return '当前查看: 未选择学生'
  const name = studentNameMap.value[selectedStudentId.value] || selectedStudentId.value
  return `当前查看: ${name} (${selectedStudentId.value})`
})

const contentViewKey = computed(() => {
  const target = teamworkEnabled.value ? `team-${selectedTeamId.value ?? 'none'}` : `student-${selectedStudentId.value || 'none'}`
  return `${problemId.value}-${target}-${contentVersion.value}`
})

const authHeaders = computed(() => ({
  headers: {
    'X-Admin-Token': adminToken,
  },
}))

const formatTime = (iso) => {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

const progressText = (team) => {
  if (Number(team.score_rate) >= 100) return '已完成'
  if (Number(team.score) > 0) return '进行中'
  return '未开始'
}

const progressClass = (team) => {
  if (Number(team.score_rate) >= 100) return 'done'
  if (Number(team.score) > 0) return 'active'
  return 'idle'
}

const toAssetPath = (href) => {
  const cleanHref = String(href || '').replace(/^\/+/, '')
  return cleanHref
    .split('/')
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join('/')
}

const createRenderer = () => {
  const renderer = new marked.Renderer()
  const originalImage = renderer.image.bind(renderer)

  renderer.image = (href, title, text) => {
    if (href && !href.startsWith('http') && !href.startsWith('//') && !href.startsWith('data:')) {
      const assetPath = toAssetPath(href)
      const encodedProblemId = encodeURIComponent(problemId.value)
      const tokenPart = adminToken ? `?token=${encodeURIComponent(adminToken)}` : ''
      const assetUrl = `${API_BASE_URL}/admin/problems/${encodedProblemId}/files/${assetPath}${tokenPart}`
      return originalImage(assetUrl, title, text)
    }
    return originalImage(href, title, text)
  }

  return renderer
}

const renderMarkdown = (source = '') => {
  return marked.parse(source, { renderer: createRenderer() })
}

const renderAttemptPlaceholders = () => {
  const root = contentCardRef.value
  if (!root) return

  const placeholders = root.querySelectorAll('.problem-input-placeholder')
  placeholders.forEach((placeholder) => {
    const inputId = placeholder.getAttribute('id') || ''
    if (!inputId) return

    const status = attemptStatus.value?.[inputId] || {}
    const answerRaw = status.last_answer
    const answer =
      answerRaw === undefined || answerRaw === null || String(answerRaw).trim() === ''
        ? '-'
        : String(answerRaw)

    const attempts = Number.isFinite(Number(status.attempts)) ? Number(status.attempts) : 0
    const maxAttempts =
      Number.isFinite(Number(status.max_attempts))
        ? Number(status.max_attempts)
        : Number.isFinite(Number(inputMeta.value?.[inputId]?.max_attempts))
          ? Number(inputMeta.value?.[inputId]?.max_attempts)
          : '-'

    const shell = document.createElement('span')
    shell.className = 'admin-answer-chip'
    if (status.correct === true) shell.classList.add('is-correct')
    if (status.correct === false && attempts > 0) shell.classList.add('is-wrong')

    const idEl = document.createElement('span')
    idEl.className = 'answer-id'
    idEl.textContent = inputId

    const valueEl = document.createElement('span')
    valueEl.className = 'answer-value'
    valueEl.textContent = answer

    const metaEl = document.createElement('span')
    metaEl.className = 'answer-meta'
    metaEl.textContent = `尝试 ${attempts}/${maxAttempts}`

    shell.appendChild(idEl)
    shell.appendChild(valueEl)
    shell.appendChild(metaEl)

    placeholder.replaceWith(shell)
  })
}

const hydrateProblemContent = async (data) => {
  problemTitle.value = data?.meta?.title || problemId.value
  state.value = data?.state || state.value
  attemptStatus.value = data?.attempt_status || {}
  contentVersion.value += 1

  const metaInputs = data?.meta?.inputs
  inputMeta.value = metaInputs && typeof metaInputs === 'object' ? metaInputs : {}

  renderedContent.value = renderMarkdown(data?.content || '')
  renderedSubproblems.value = (data?.subproblems || []).map((block) => ({
    ...block,
    html: renderMarkdown(block.content || ''),
  }))

  renderSequence.value = (data?.render_sequence || []).map((segment, index) => {
    if (segment.type === 'plain') {
      return {
        key: `plain-${index}`,
        type: 'plain',
        html: renderMarkdown(segment.content || ''),
      }
    }
    return {
      key: `sub-${segment.subproblem_no}-${index}`,
      type: 'subproblem',
      subproblem_no: segment.subproblem_no,
    }
  })

  await nextTick()
  renderAttemptPlaceholders()
}

const loadProblemContent = async () => {
  const params = {}
  if (teamworkEnabled.value && selectedTeamId.value !== null) {
    params.team_id = selectedTeamId.value
  }
  if (!teamworkEnabled.value && selectedStudentId.value) {
    params.student_id = selectedStudentId.value
  }

  const res = await axios.get(
    `${API_BASE_URL}/admin/problems/${encodeURIComponent(problemId.value)}/content`,
    {
      ...authHeaders.value,
      params,
    },
  )
  await hydrateProblemContent(res.data)
}

const loadTeamOverview = async () => {
  const res = await axios.get(
    `${API_BASE_URL}/admin/teamwork/${encodeURIComponent(problemId.value)}/overview`,
    authHeaders.value,
  )
  teamworkConfig.value = res.data?.config || null
  teams.value = res.data?.teams || []
}

const loadTeamRanking = async () => {
  const rankingRes = await axios.get(
    `${API_BASE_URL}/admin/problems/${encodeURIComponent(problemId.value)}/ranking`,
    {
      ...authHeaders.value,
      params: { scope: 'team' },
    },
  )

  const mapping = {}
  for (const row of rankingRes.data || []) {
    mapping[row.team_id] = row
  }
  teamRankingMap.value = mapping
}

const loadStudentRanking = async () => {
  const rankingRes = await axios.get(
    `${API_BASE_URL}/admin/problems/${encodeURIComponent(problemId.value)}/ranking`,
    authHeaders.value,
  )
  rankingRows.value = rankingRes.data || []
}

const loadStudentOptions = async () => {
  const res = await axios.get(`${API_BASE_URL}/admin/students`, authHeaders.value)
  const rows = Array.isArray(res.data) ? res.data : []
  studentOptions.value = rows
    .filter((row) => !row?.is_deleted)
    .map((row) => ({
      student_id: row.student_id,
      name: row.name || row.student_id,
    }))
    .sort((a, b) => String(a.student_id).localeCompare(String(b.student_id)))
}

const saveTeamCount = async (nextTeamCount) => {
  if (!teamworkEnabled.value) {
    return
  }

  savingTeamConfig.value = true
  try {
    await axios.put(
      `${API_BASE_URL}/admin/teamwork/${encodeURIComponent(problemId.value)}/config`,
      { team_count: nextTeamCount },
      authHeaders.value,
    )

    await loadTeamOverview()
    await loadTeamRanking()
    await loadStudentRanking()

    if (!teamRows.value.some((item) => item.team_id === selectedTeamId.value)) {
      selectedTeamId.value = teamRows.value.length > 0 ? teamRows.value[0].team_id : null
    }

    await loadProblemContent()
  } catch (e) {
    alert(e.response?.data?.detail || '更新队伍数量失败')
  } finally {
    savingTeamConfig.value = false
  }
}

const onTeamChange = async (nextTeamId) => {
  if (typeof nextTeamId === 'number') {
    selectedTeamId.value = nextTeamId
  }
  await loadProblemContent()
}

const onStudentChange = async (nextStudentId) => {
  if (typeof nextStudentId === 'string') {
    selectedStudentId.value = nextStudentId
  }
  await loadProblemContent()
}

const loadPage = async () => {
  if (!adminToken) {
    router.push('/admin')
    return
  }

  loading.value = true
  error.value = ''

  try {
    await loadTeamOverview()

    if (teamworkEnabled.value) {
      await loadTeamRanking()
      await loadStudentRanking()
      if (teamRows.value.length > 0 && selectedTeamId.value === null) {
        selectedTeamId.value = teamRows.value[0].team_id
      }
    } else {
      await Promise.all([loadStudentOptions(), loadStudentRanking()])
      if (!selectedStudentId.value) {
        if (rankingRows.value.length > 0) {
          selectedStudentId.value = rankingRows.value[0].student_id
        } else if (studentOptions.value.length > 0) {
          selectedStudentId.value = studentOptions.value[0].student_id
        }
      }
    }

    await loadProblemContent()
  } catch (e) {
    if (e.response?.status === 401) {
      localStorage.removeItem('adminToken')
      router.push('/admin')
      return
    }
    if (e.response?.status === 404) {
      error.value = '题目不存在、目标学生/队伍不存在，或题目已被删除。'
      return
    }
    error.value = e.response?.data?.detail || '加载失败，请稍后重试。'
  } finally {
    loading.value = false
    await nextTick()
    renderAttemptPlaceholders()
  }
}

const goBack = () => {
  router.push({ path: '/admin', query: { tab: 'problems' } })
}

onMounted(async () => {
  await loadPage()
})
</script>

<style scoped>
.admin-problem-detail-page {
  min-height: 100vh;
  background: #f4f6fb;
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.back-btn {
  border: 1px solid #d1d9e6;
  background: #fff;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  color: #374151;
}

.back-btn:hover {
  background: #eff6ff;
  border-color: #93c5fd;
}

h1 {
  margin: 0;
  font-size: 24px;
  color: #1f2937;
}

.problem-id {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.state-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.badge {
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  border: 1px solid transparent;
}

.badge.ok {
  color: #166534;
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.badge.warn {
  color: #92400e;
  background: #fffbeb;
  border-color: #fde68a;
}

.badge.danger {
  color: #991b1b;
  background: #fef2f2;
  border-color: #fecaca;
}

.badge.neutral {
  color: #475569;
  background: #f8fafc;
  border-color: #e2e8f0;
}

.content-layout {
  display: grid;
  gap: 16px;
  grid-template-columns: 1.5fr 1fr;
}

.card {
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  padding: 18px;
}

.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.card-title-row h2 {
  margin: 0;
  font-size: 18px;
  color: #111827;
}

.content-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.deadline-text,
.meta-text {
  color: #6b7280;
  font-size: 13px;
}

.viewer-tag {
  font-size: 12px;
  color: #1e40af;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  padding: 4px 10px;
}

.markdown-body {
  color: #1f2937;
  line-height: 1.75;
}

.problem-content {
  margin-bottom: 14px;
}

.subproblem-card {
  border: 1px solid #dbeafe;
  background: #f8fbff;
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 12px;
}

.subproblem-header {
  margin-bottom: 8px;
  color: #1d4ed8;
}

:deep(.admin-answer-chip) {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin: 0 4px;
  padding: 3px 8px;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  vertical-align: middle;
}

:deep(.admin-answer-chip .answer-id) {
  font-size: 11px;
  color: #475569;
  font-weight: 700;
}

:deep(.admin-answer-chip .answer-value) {
  font-size: 13px;
  color: #0f172a;
  font-weight: 700;
}

:deep(.admin-answer-chip .answer-meta) {
  font-size: 11px;
  color: #64748b;
}

:deep(.admin-answer-chip.is-correct) {
  background: #f0fdf4;
  border-color: #86efac;
}

:deep(.admin-answer-chip.is-wrong) {
  background: #fef2f2;
  border-color: #fecaca;
}

.loading-state,
.error-state,
.empty-members {
  text-align: center;
  padding: 24px;
  color: #64748b;
}

.error-state {
  color: #b91c1c;
}

@media (max-width: 1080px) {
  .content-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .admin-problem-detail-page {
    padding: 14px;
  }

  .page-header {
    flex-direction: column;
  }

  .header-left {
    flex-direction: column;
  }

}
</style>
