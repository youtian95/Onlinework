<template>
  <div class="problem-container">
    <div class="nav-bar">
      <button @click="router.push('/problems')" class="back-btn">← 返回列表</button>
      <div class="nav-right">
        <template v-if="teamworkEnabled && showProblemBody && token">
          <span class="score-badge team">队伍得分: {{ teamCurrentScore }} / {{ totalScore }}</span>
          <span v-if="myClaimTotalScore > 0" class="score-badge mine">我的子题: {{ myClaimScore }} / {{ myClaimTotalScore }}</span>
          <span v-if="currentTeamLabel" class="team-badge">{{ currentTeamLabel }}</span>
        </template>
        <span v-else-if="totalScore > 0 && studentId" class="score-badge">当前得分: {{ personalCurrentScore }} / {{ totalScore }}</span>
        <span class="user-badge">{{ studentId ? studentId : '游客' }}</span>
      </div>
    </div>

    <div v-if="loading" class="loading-state">加载题目中...</div>
    <div v-else>
      <div v-if="isTerminated" class="terminated-banner">
        作业已截止 ({{ formatTime(deadline) }})，仅供查看，无法提交。
      </div>

      <div v-if="!token" class="guest-banner">
        当前为游客浏览模式，无法保存团队状态，也不能上传 PDF。
      </div>

      <div v-if="teamworkEnabled && token" class="team-panel-entry card-shell">
        <div class="team-panel-entry-text">
          <strong>{{ teamJoined ? '已加入队伍' : '尚未加入队伍' }}</strong>
          <span>{{ teamJoined ? `当前队伍：${currentTeamLabel}` : '点击按钮选择队伍后才能开始作答' }}</span>
        </div>
        <button type="button" class="team-panel-open-btn" @click="showTeamPanel = true">
          {{ teamJoined ? '查看队伍' : '选择队伍' }}
        </button>
      </div>

      <div v-if="teamworkEnabled && token && !teamJoined" class="team-required-hint card-shell">
        <h3>当前题目需要先加入队伍</h3>
        <p>点击上方“选择队伍”按钮后会弹出队伍列表。</p>
      </div>

      <div v-if="teamworkEnabled && token && showTeamPanel" class="team-modal-overlay" @click.self="showTeamPanel = false">
        <div class="team-modal-card">
          <div class="team-modal-header">
            <h3>队伍选择与成员查看</h3>
            <button type="button" class="team-modal-close" @click="showTeamPanel = false">×</button>
          </div>
          <TeamSelectionPanel
            :team-joined="teamJoined"
            :team-info="teamInfo"
            :team-config="teamConfig"
            :team-rows="teamRows"
            :my-claim-subproblem="myClaimSubproblem"
            @join-team="joinTeam"
          />
        </div>
      </div>

      <template v-if="showProblemBody">
        <ProblemSheet
          ref="problemSheetRef"
          :teamwork-enabled="teamworkEnabled"
          :render-sequence="renderSequence"
          :rendered-content="renderedContent"
          :rendered-subproblems="renderedSubproblems"
          :subproblem-map="subproblemMap"
          :student-id="studentId"
          :token="token"
          :is-subproblem-open="isSubproblemOpen"
          :get-subproblem-card-class="getSubproblemCardClass"
          :get-subproblem-state-text="getSubproblemStateText"
          :get-claim-button-kind="getClaimButtonKind"
          :is-claim-button-disabled="isClaimButtonDisabled"
          :get-claim-button-text="getClaimButtonText"
          :get-claim-for-subproblem="getClaimForSubproblem"
          @toggle-subproblem="toggleSubproblem"
          @claim-subproblem="claimSubproblem"
        />

        <div class="actions" v-if="!isTerminated">
          <div v-if="token" class="pdf-upload-panel">
            <label class="pdf-upload-label" for="pdf-upload-input">作业 PDF：</label>
            <input
              id="pdf-upload-input"
              ref="pdfInputRef"
              class="pdf-upload-input"
              type="file"
              accept="application/pdf,.pdf"
              @change="onPdfFileChange"
            >
            <button class="pdf-upload-btn" type="button" @click="uploadPdf" :disabled="!selectedPdfFile || uploadingPdf">
              {{ uploadingPdf ? '上传中...' : '上传 PDF' }}
            </button>
            <div class="pdf-upload-status">
              <span v-if="selectedPdfName">待上传：{{ selectedPdfName }}</span>
              <span v-else-if="hasUploadedPdf">已保存：{{ uploadedPdfName || '已上传 PDF' }}</span>
              <span v-else>上传答题计算过程 PDF 文件</span>
            </div>
          </div>

          <div class="hint-text">{{ hintText }}</div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { marked } from 'marked'
import markedKatex from 'marked-katex-extension'
import TeamSelectionPanel from '../components/student/TeamSelectionPanel.vue'
import ProblemSheet from '../components/student/ProblemSheet.vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

marked.use(markedKatex({ throwOnError: false, trust: true, strict: 'ignore' }))

const route = useRoute()
const router = useRouter()
const studentId = localStorage.getItem('studentId') || ''
const token = localStorage.getItem('studentToken') || ''
const problemId = route.params.id
const scrollStorageKey = `problem-detail-scroll:${studentId || 'guest'}:${problemId}`

const loading = ref(true)
const renderedContent = ref('')
const renderedSubproblems = ref([])
const renderSequence = ref([])
const inputIds = ref([])
const userAnswers = ref({})
const attemptStatus = ref({})
const meta = ref({})
const isTerminated = ref(false)
const deadline = ref(null)
const selectedPdfFile = ref(null)
const selectedPdfName = ref('')
const uploadedPdfName = ref('')
const hasUploadedPdf = ref(false)
const pdfInputRef = ref(null)
const uploadingPdf = ref(false)
const teamworkEnabled = ref(false)
const teamJoined = ref(false)
const teamInfo = ref(null)
const teamConfig = ref(null)
const teamRows = ref([])
const teamClaims = ref([])
const myClaimSubproblem = ref(null)
const openSubproblems = ref([])
const problemSheetRef = ref(null)
const showTeamPanel = ref(false)
let bindScheduled = false

const saveScrollPosition = () => {
  try {
    const y = Math.max(0, Math.round(window.scrollY || window.pageYOffset || 0))
    sessionStorage.setItem(scrollStorageKey, String(y))
  } catch {
    // ignore storage failures
  }
}

const restoreScrollPosition = () => {
  try {
    const raw = sessionStorage.getItem(scrollStorageKey)
    if (!raw) return
    const y = Number(raw)
    if (!Number.isFinite(y) || y < 0) return
    window.scrollTo({ top: y, left: 0, behavior: 'auto' })
  } catch {
    // ignore storage failures
  }
}

const restoreScrollPositionStable = () => {
  // Restore multiple times to handle late layout changes (images/async render).
  restoreScrollPosition()
  requestAnimationFrame(() => restoreScrollPosition())
  setTimeout(() => restoreScrollPosition(), 120)
  setTimeout(() => restoreScrollPosition(), 300)
}

const metaInputs = computed(() => {
  const inputs = meta.value?.inputs
  if (!inputs || Array.isArray(inputs)) return {}
  return inputs
})

const uniqueInputIds = computed(() => [...new Set(inputIds.value)])

const totalScore = computed(() => {
  if (!uniqueInputIds.value.length) return 0
  return uniqueInputIds.value.reduce((sum, id) => sum + (metaInputs.value[id]?.score ?? 1), 0)
})

const teamCurrentScore = computed(() => {
  return uniqueInputIds.value.reduce((sum, id) => {
    if (!attemptStatus.value[id]?.correct) return sum
    return sum + (metaInputs.value[id]?.score ?? 1)
  }, 0)
})

const myClaimBlock = computed(() => {
  return renderedSubproblems.value.find((block) => block.subproblem_no === myClaimSubproblem.value) || null
})

const myClaimTotalScore = computed(() => {
  if (!myClaimBlock.value) return 0
  return myClaimBlock.value.input_ids.reduce((sum, id) => sum + (metaInputs.value[id]?.score ?? 1), 0)
})

const myClaimScore = computed(() => {
  if (!myClaimBlock.value) return 0
  return myClaimBlock.value.input_ids.reduce((sum, id) => {
    if (!attemptStatus.value[id]?.correct) return sum
    return sum + (metaInputs.value[id]?.score ?? 1)
  }, 0)
})

const personalCurrentScore = computed(() => {
  if (teamworkEnabled.value) {
    return myClaimScore.value
  }
  return teamCurrentScore.value
})

const currentTeamLabel = computed(() => {
  if (!teamInfo.value) return ''
  if (teamInfo.value.team_name) return teamInfo.value.team_name
  if (teamInfo.value.team_no) return `第 ${teamInfo.value.team_no} 队`
  return '已入队'
})

const teamClaimMap = computed(() => {
  const claimMap = {}
  for (const claim of teamClaims.value) {
    claimMap[claim.subproblem_no] = claim
  }
  return claimMap
})

const subproblemMap = computed(() => {
  const mapping = {}
  for (const block of renderedSubproblems.value) {
    mapping[block.subproblem_no] = block
  }
  return mapping
})

const showProblemBody = computed(() => !teamworkEnabled.value || !token || teamJoined.value)

const hintText = computed(() => {
  if (!token) {
    return '提示：游客模式下按 Enter 可以即时校验，但不会保存团队状态。'
  }
  if (teamworkEnabled.value && !myClaimSubproblem.value) {
    return '提示：先认领一个子问题，再在自己负责的区域内按 Enter 提交单个输入框。'
  }
  if (teamworkEnabled.value) {
    return '提示：PDF中写自己负责的子题目的计算过程。'
  }
  return '提示：输入答案后按 Enter 键提交单个输入框。'
})

const formatTime = (iso) => (iso ? new Date(iso).toLocaleString() : '-')

const authConfig = () => {
  if (!token) return {}
  return { headers: { Authorization: `Bearer ${token}` } }
}

const handleAuthExpired = () => {
  localStorage.removeItem('studentToken')
  localStorage.removeItem('studentId')
  localStorage.removeItem('studentName')
  router.push('/')
}

const persistTeamMembership = (team) => {
  const raw = localStorage.getItem('problemTeamMemberships')
  let mapping = {}
  if (raw) {
    try {
      mapping = JSON.parse(raw)
    } catch {
      mapping = {}
    }
  }
  mapping[String(problemId)] = {
    team_no: team?.team_no ?? null,
    team_name: team?.team_name ?? null,
  }
  localStorage.setItem('problemTeamMemberships', JSON.stringify(mapping))
}

const clearTeamMembership = () => {
  const raw = localStorage.getItem('problemTeamMemberships')
  if (!raw) return
  try {
    const mapping = JSON.parse(raw)
    delete mapping[String(problemId)]
    localStorage.setItem('problemTeamMemberships', JSON.stringify(mapping))
  } catch {
    localStorage.removeItem('problemTeamMemberships')
  }
}

const createRenderer = () => {
  const renderer = new marked.Renderer()
  const originalImage = renderer.image.bind(renderer)
  renderer.image = (href, title, text) => {
    if (href && !href.startsWith('http') && !href.startsWith('//') && !href.startsWith('data:')) {
      const cleanHref = href.startsWith('/') ? href.slice(1) : href
      const baseUrl = `${API_BASE_URL}/problems/${problemId}/${cleanHref}`
      const sep = baseUrl.includes('?') ? '&' : '?'
      const authedUrl = token ? `${baseUrl}${sep}token=${encodeURIComponent(token)}` : baseUrl
      return originalImage(authedUrl, title, text)
    }
    return originalImage(href, title, text)
  }
  return renderer
}

const renderMarkdown = (source = '') => {
  return marked.parse(source, { renderer: createRenderer() })
}

const scheduleBindInputs = () => {
  if (bindScheduled) return
  bindScheduled = true
  nextTick(() => {
    requestAnimationFrame(() => {
      bindScheduled = false
      bindInputs()
    })
  })
}

const setDefaultOpenSubproblems = () => {
  if (!renderedSubproblems.value.length) {
    openSubproblems.value = []
    return
  }
  if (teamworkEnabled.value && myClaimSubproblem.value) {
    openSubproblems.value = [myClaimSubproblem.value]
    return
  }
  if (teamworkEnabled.value) {
    openSubproblems.value = []
    return
  }
  openSubproblems.value = []
}

const hydrateProblemData = async (data) => {
  renderedContent.value = renderMarkdown(data.content || '')
  renderedSubproblems.value = (data.subproblems || []).map((block) => ({
    ...block,
    html: renderMarkdown(block.content || ''),
  }))
  renderSequence.value = (data.render_sequence || []).map((segment, index) => {
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
  inputIds.value = [...new Set(data.input_ids || [])]
  attemptStatus.value = data.attempt_status || {}
  meta.value = data.meta || {}
  isTerminated.value = !!data.is_terminated
  deadline.value = data.deadline
  hasUploadedPdf.value = !!data.pdf_uploaded
  uploadedPdfName.value = data.pdf_filename || ''
  teamworkEnabled.value = !!data.teamwork_enabled || teamworkEnabled.value
  if (teamworkEnabled.value) {
    teamClaims.value = data.team_claims || []
    myClaimSubproblem.value = data.my_claim_subproblem ?? null
  } else {
    teamClaims.value = []
    myClaimSubproblem.value = null
  }
  setDefaultOpenSubproblems()
  scheduleBindInputs()
}

const loadTeamState = async () => {
  if (!token) return null
  const res = await axios.get(`${API_BASE_URL}/problems/${problemId}/team/me`, authConfig())
  teamworkEnabled.value = !!res.data?.teamwork_enabled
  teamJoined.value = !!res.data?.joined
  teamInfo.value = res.data?.team || null
  if (teamJoined.value && teamInfo.value) {
    persistTeamMembership(teamInfo.value)
  } else if (teamworkEnabled.value) {
    clearTeamMembership()
  }
  return res.data
}

const loadTeams = async () => {
  if (!token || !teamworkEnabled.value) return
  const res = await axios.get(`${API_BASE_URL}/problems/${problemId}/teams`, authConfig())
  teamRows.value = res.data?.teams || []
  teamConfig.value = res.data?.config || null
}

const loadProblem = async () => {
  const res = await axios.get(`${API_BASE_URL}/problems/${problemId}`, authConfig())
  await hydrateProblemData(res.data)
}

const loadPage = async () => {
  loading.value = true
  try {
    if (token) {
      const teamState = await loadTeamState()
      if (teamState?.teamwork_enabled) {
        await loadTeams()
        if (!teamState.joined) {
          return
        }
      }
    }
    await loadProblem()
  } catch (e) {
    if (e.response?.status === 401) {
      alert('登录已过期或未授权')
      handleAuthExpired()
      return
    }
    if (e.response?.status === 403 && e.response?.data?.detail === 'Team selection required') {
      teamworkEnabled.value = true
      teamJoined.value = false
      await loadTeams()
      return
    }
    if (e.response?.status === 403) {
      alert('题目未发布或无权限访问')
      router.push('/problems')
      return
    }
    if (e.response?.status === 404) {
      alert('题目不存在')
      router.push('/problems')
      return
    }
    alert('加载题目失败:' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  window.addEventListener('scroll', saveScrollPosition, { passive: true })
  window.addEventListener('beforeunload', saveScrollPosition)
  await loadPage()
  restoreScrollPositionStable()
})

onBeforeUnmount(() => {
  saveScrollPosition()
  window.removeEventListener('scroll', saveScrollPosition)
  window.removeEventListener('beforeunload', saveScrollPosition)
})

const isSubproblemOpen = (subproblemNo) => openSubproblems.value.includes(subproblemNo)

const toggleSubproblem = async (subproblemNo) => {
  if (isSubproblemOpen(subproblemNo)) {
    openSubproblems.value = openSubproblems.value.filter((item) => item !== subproblemNo)
    return
  }
  openSubproblems.value = [...openSubproblems.value, subproblemNo]
  scheduleBindInputs()
}

const getClaimForSubproblem = (subproblemNo) => teamClaimMap.value[subproblemNo] || null

const getSubproblemCardClass = (block) => {
  const claim = getClaimForSubproblem(block.subproblem_no)
  return {
    mine: claim?.student_id === studentId,
    locked: !!claim && claim.student_id !== studentId,
    open: isSubproblemOpen(block.subproblem_no),
  }
}

const getSubproblemStateText = (block) => {
  const claim = getClaimForSubproblem(block.subproblem_no)
  if (!claim) return '未认领'
  if (claim.student_id === studentId) return '你正在负责'
  return `${claim.name || claim.student_id} 负责中`
}

const getClaimButtonText = (block) => {
  const claim = getClaimForSubproblem(block.subproblem_no)
  if (!teamJoined.value) return '先选队'
  if (!claim) return '认领'
  if (claim.student_id === studentId) return '已认领'
  return '已被占用'
}

const getClaimButtonKind = (block) => {
  const claim = getClaimForSubproblem(block.subproblem_no)
  if (!claim) return 'primary'
  if (claim.student_id === studentId) return 'secondary'
  return 'disabled'
}

const isClaimButtonDisabled = (block) => {
  if (!token || !teamJoined.value) return true
  const claim = getClaimForSubproblem(block.subproblem_no)
  return !!claim
}

const buildTeamSwitchConfirm = (detail) => {
  const fromText = detail?.current_team_no ? `第 ${detail.current_team_no} 队` : '当前队伍'
  const toText = detail?.target_team_no ? `第 ${detail.target_team_no} 队` : '目标队伍'
  return `从 ${fromText} 切换到 ${toText} 会清空你在这道题里的认领、作答和 PDF 记录，继续吗？`
}

const buildClaimSwitchConfirm = (detail) => {
  const fromText = detail?.current_subproblem_no ? `子题 ${detail.current_subproblem_no}` : '当前子题'
  const toText = detail?.target_subproblem_no ? `子题 ${detail.target_subproblem_no}` : '目标子题'
  return `从 ${fromText} 切换到 ${toText} 会清空你之前的提交记录。注意：每道团队题只能切换一次认领，本次确认会消耗这次切换机会，继续吗？`
}

const joinTeam = async (teamNo, forceSwitch = false) => {
  try {
    const res = await axios.post(
      `${API_BASE_URL}/problems/${problemId}/team/join`,
      { team_no: teamNo, force_switch: forceSwitch },
      authConfig(),
    )
    teamJoined.value = true
    teamInfo.value = {
      team_no: res.data.team_no,
      team_name: res.data.team_name,
    }
    showTeamPanel.value = false
    persistTeamMembership(teamInfo.value)
    await loadTeams()
    await loadProblem()
  } catch (e) {
    if (e.response?.status === 401) {
      alert('登录已过期或未授权')
      handleAuthExpired()
      return
    }
    if (e.response?.status === 409 && e.response?.data?.detail?.requires_confirmation) {
      if (window.confirm(buildTeamSwitchConfirm(e.response.data.detail))) {
        await joinTeam(teamNo, true)
      }
      return
    }
    alert(e.response?.data?.detail?.message || e.response?.data?.detail || '加入队伍失败')
  }
}

const claimSubproblem = async (subproblemNo, forceSwitch = false) => {
  if (!token || !teamJoined.value) return

  if (!forceSwitch && myClaimSubproblem.value && myClaimSubproblem.value !== subproblemNo) {
    const shouldSwitch = window.confirm(
      buildClaimSwitchConfirm({
        current_subproblem_no: myClaimSubproblem.value,
        target_subproblem_no: subproblemNo,
      }),
    )
    if (!shouldSwitch) return
    forceSwitch = true
  }

  try {
    const res = await axios.post(
      `${API_BASE_URL}/problems/${problemId}/team/claim`,
      { subproblem_no: subproblemNo, force_switch: forceSwitch },
      authConfig(),
    )
    myClaimSubproblem.value = res.data.subproblem_no
    await loadProblem()
  } catch (e) {
    const detail = e.response?.data?.detail
    if (e.response?.status === 401) {
      alert('登录已过期或未授权')
      handleAuthExpired()
      return
    }
    if (e.response?.status === 409 && detail?.requires_confirmation) {
      if (window.confirm(buildClaimSwitchConfirm(detail))) {
        await claimSubproblem(subproblemNo, true)
      }
      return
    }
    if (e.response?.status === 409 && detail?.message === 'Subproblem switch limit reached') {
      alert('认领只能切换一次，你已用完切换次数。')
      return
    }
    alert(detail?.message || detail || '认领子题失败')
  }
}

const onPdfFileChange = (event) => {
  const file = event?.target?.files?.[0]
  if (!file) {
    selectedPdfFile.value = null
    selectedPdfName.value = ''
    return
  }

  const lowerName = (file.name || '').toLowerCase()
  const contentType = (file.type || '').toLowerCase()
  const isPdf = lowerName.endsWith('.pdf') || contentType === 'application/pdf'

  if (!isPdf) {
    alert('仅支持上传 PDF 文件。')
    if (pdfInputRef.value) {
      pdfInputRef.value.value = ''
    }
    selectedPdfFile.value = null
    selectedPdfName.value = ''
    return
  }

  selectedPdfFile.value = file
  selectedPdfName.value = file.name
}

const uploadPdf = async () => {
  if (!token) return
  if (!selectedPdfFile.value) {
    alert('请先选择一个 PDF 文件。')
    return
  }

  try {
    uploadingPdf.value = true
    const formData = new FormData()
    formData.append('pdf', selectedPdfFile.value)

    const res = await axios.post(
      `${API_BASE_URL}/problems/${problemId}/pdf`,
      formData,
      authConfig(),
    )

    hasUploadedPdf.value = !!res.data?.pdf_uploaded
    uploadedPdfName.value = res.data?.pdf_filename || selectedPdfName.value
    selectedPdfFile.value = null
    selectedPdfName.value = ''
    if (pdfInputRef.value) {
      pdfInputRef.value.value = ''
    }
    alert('PDF 上传成功。')
  } catch (e) {
    if (e.response?.status === 401 || e.response?.status === 403) {
      alert(e.response?.data?.detail || '登录已过期或未授权')
      if (e.response?.status === 401) {
        handleAuthExpired()
      }
    } else {
      alert(e.response?.data?.detail || 'PDF 上传失败')
    }
  } finally {
    uploadingPdf.value = false
  }
}

const bindInputs = () => {
  const sheetRef = problemSheetRef.value
  const sheetRoot = typeof sheetRef?.getRootEl === 'function' ? sheetRef.getRootEl() : sheetRef
  if (sheetRoot) {
    bindInputsInContainer(sheetRoot)
  }
  applyAttemptStatusToInputs(attemptStatus.value)
}

const bindInputsInContainer = (container) => {
  if (!container || typeof container.querySelectorAll !== 'function') return
  const placeholders = container.querySelectorAll('.problem-input-placeholder')
  placeholders.forEach((placeholder) => {
    if (placeholder.dataset.processed) return
    const id = placeholder.id
    if (id && uniqueInputIds.value.includes(id)) {
      processPlaceholder(placeholder, id)
    }
  })
}

const getInputPlaceholder = (status) => {
  if (!token) return '按回车验证'
  if (isTerminated.value) return '已截止'
  if (teamworkEnabled.value) {
    if (!status.owner_student_id) return '未认领'
    if (!status.editable) return '队友负责'
  }
  if (status.correct) return '已正确'
  if (status.locked) return '已锁定'
  return '请输入答案'
}

const getInputStatusText = (status) => {
  if (!token) return '游客验证'
  if (teamworkEnabled.value) {
    if (!status.owner_student_id) return '未认领'
    if (!status.editable) return `队友 ${status.owner_student_id} 负责`
  }
  if (status.correct) return '已正确'
  if (status.locked) return '已锁定'
  return `剩余 ${status.remaining} 次`
}

const resolveInputDisabled = (status) => {
  if (!token) return false
  if (isTerminated.value) return true
  if (teamworkEnabled.value) {
    if (!status.owner_student_id) return true
    if (!status.editable) return true
  }
  return status.correct || status.locked
}

const processPlaceholder = (placeholder, id) => {
  placeholder.dataset.processed = 'true'
  const status = attemptStatus.value[id] || {
    remaining: 0,
    locked: false,
    correct: false,
    editable: !teamworkEnabled.value,
    owner_student_id: null,
    last_answer: '',
  }

  const input = document.createElement('input')
  input.type = 'text'
  input.className = 'problem-input-field'
  input.dataset.id = id
  input.placeholder = getInputPlaceholder(status)
  input.disabled = resolveInputDisabled(status)
  input.value = status.last_answer || userAnswers.value[id] || ''

  if (input.value && !userAnswers.value[id]) {
    userAnswers.value[id] = input.value
  }

  input.oninput = (event) => {
    const nextValue = event.target.value
    userAnswers.value[id] = nextValue
    document.querySelectorAll(`.problem-input-field[data-id="${id}"]`).forEach((otherInput) => {
      if (otherInput !== input) {
        otherInput.value = nextValue
      }
    })
  }

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      submitSingleAnswer(id)
    }
  })

  const info = document.createElement('span')
  info.className = 'attempt-info'
  info.dataset.id = id
  info.textContent = getInputStatusText(status)

  const wrapper = document.createElement('span')
  wrapper.className = 'input-wrapper'
  wrapper.appendChild(input)
  wrapper.appendChild(info)
  placeholder.replaceWith(wrapper)
}

const applyAttemptStatusToInputs = (statusMap) => {
  document.querySelectorAll('.problem-input-field').forEach((input) => {
    const id = input.dataset.id
    const status = statusMap[id]
    if (!status) return

    input.disabled = resolveInputDisabled(status)
    input.placeholder = getInputPlaceholder(status)
    input.classList.toggle('readonly-team', teamworkEnabled.value && !!status.owner_student_id && !status.editable)

    if (status.last_answer !== undefined) {
      input.value = status.last_answer
      userAnswers.value[id] = status.last_answer
    } else if (userAnswers.value[id]) {
      input.value = userAnswers.value[id]
    }
  })

  document.querySelectorAll('.attempt-info').forEach((info) => {
    const id = info.dataset.id
    const status = statusMap[id]
    if (!status) return
    info.textContent = getInputStatusText(status)
  })
}

const updateInputStyleDOM = (input, isCorrect) => {
  if (!input) return

  if (isCorrect === true) {
    input.classList.add('correct')
    input.classList.remove('incorrect')
    input.style.borderColor = '#16a34a'
    input.style.backgroundColor = '#f0fdf4'
    input.blur()
    return
  }

  if (isCorrect === false) {
    input.classList.add('incorrect')
    input.style.borderColor = '#dc2626'
    input.style.backgroundColor = '#fef2f2'
    input.classList.remove('shake')
    void input.offsetWidth
    input.classList.add('shake')
    setTimeout(() => input.classList.remove('shake'), 400)
  }
}

const submitSingleAnswer = async (inputId) => {
  if (teamworkEnabled.value) {
    const status = attemptStatus.value[inputId]
    if (!status?.editable) {
      alert('只能提交自己认领的子问题区域。')
      return
    }
  }

  let currentValue = userAnswers.value[inputId]
  if (currentValue === null || currentValue === undefined) {
    currentValue = ''
  } else {
    currentValue = String(currentValue).trim()
  }

  const singleAnswer = { [inputId]: currentValue }

  try {
    const res = await axios.post(
      `${API_BASE_URL}/problems/submit`,
      {
        problem_id: problemId,
        answers: singleAnswer,
      },
      authConfig(),
    )

    if (!token) {
      const isCorrect = res.data.results?.[inputId]
      const info = document.querySelector(`.attempt-info[data-id="${inputId}"]`)
      const input = document.querySelector(`.problem-input-field[data-id="${inputId}"]`)
      if (info) {
        info.textContent = isCorrect ? '正确' : '错误'
      }
      if (input) {
        updateInputStyleDOM(input, isCorrect)
      }
      return
    }

    attemptStatus.value = res.data.attempt_status || {}
    const isCorrect = res.data.results?.[inputId]
    document.querySelectorAll(`.problem-input-field[data-id="${inputId}"]`).forEach((input) => {
      updateInputStyleDOM(input, isCorrect)
    })
    applyAttemptStatusToInputs(attemptStatus.value)
  } catch (e) {
    if (e.response?.status === 401 || e.response?.status === 403) {
      alert(e.response?.data?.detail || '登录已过期或未授权')
      if (e.response?.status === 401) {
        handleAuthExpired()
      }
      return
    }
    if (e.response?.status === 400) {
      alert(e.response?.data?.detail || '提交参数错误')
      return
    }
    console.error(e)
    alert(e.response?.data?.detail || '提交失败')
  }
}
</script>

<style>
.markdown-body {
  line-height: 1.8;
  font-size: 16px;
  color: #243041;
}

.markdown-body p {
  margin-bottom: 1em;
}

.problem-input-field {
  border: 1px solid #d7dee8;
  border-radius: 10px;
  padding: 6px 10px;
  margin: 0 3px;
  width: 96px;
  font-family: inherit;
  font-size: 0.9em;
  text-align: center;
  transition: all 0.25s;
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
}

.problem-input-field:focus {
  border-color: #2563eb;
  outline: none;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.14);
}

.problem-input-field:disabled {
  background-color: #f8fafc;
  color: #94a3b8;
  cursor: not-allowed;
}

.problem-input-field.readonly-team {
  border-style: dashed;
}

.problem-input-field.shake {
  animation: inputShake 0.35s ease-in-out;
}

@keyframes inputShake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-5px); }
  40% { transform: translateX(5px); }
  60% { transform: translateX(-4px); }
  80% { transform: translateX(4px); }
}

.input-wrapper {
  display: inline-flex;
  position: relative;
  vertical-align: middle;
  align-items: center;
  margin: 3px 3px;
}

.attempt-info {
  position: absolute;
  top: 115%;
  left: 50%;
  transform: translateX(-50%);
  background-color: rgba(15, 23, 42, 0.88);
  color: #fff;
  padding: 5px 10px;
  border-radius: 8px;
  font-size: 12px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s, top 0.2s;
  z-index: 100;
}

.attempt-info::after {
  content: '';
  position: absolute;
  bottom: 100%;
  left: 50%;
  margin-left: -5px;
  border-width: 5px;
  border-style: solid;
  border-color: transparent transparent rgba(15, 23, 42, 0.88) transparent;
}

.input-wrapper:hover .attempt-info {
  opacity: 1;
  top: 128%;
}

.katex-display {
  margin: 0.5em 0 !important;
  padding: 2px 0;
}
</style>

<style scoped>
.problem-container {
  max-width: 1120px;
  margin: 32px auto 48px;
  padding: 0 20px 24px;
}

.card-shell {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, #ffffff 100%);
  border: 1px solid #e5ecf3;
  border-radius: 24px;
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.06);
}

.nav-bar {
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 18px 24px;
  background: linear-gradient(135deg, #f7fbff 0%, #ffffff 100%);
  border: 1px solid #e5ecf3;
  border-radius: 22px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.05);
}

.nav-right {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.score-badge,
.team-badge,
.user-badge {
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 13px;
  font-weight: 600;
}

.score-badge {
  color: #166534;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}

.score-badge.team {
  color: #1d4ed8;
  background: #eff6ff;
  border-color: #bfdbfe;
}

.score-badge.mine {
  color: #7c2d12;
  background: #fff7ed;
  border-color: #fed7aa;
}

.team-badge {
  color: #0f766e;
  background: #ecfeff;
  border: 1px solid #a5f3fc;
}

.user-badge {
  color: #334155;
  background: #f8fafc;
  border: 1px solid #dbe4ee;
}

.back-btn {
  background: none;
  border: 1px solid #cfd8e3;
  color: #475569;
  cursor: pointer;
  font-size: 15px;
  border-radius: 999px;
  padding: 10px 16px;
  transition: all 0.2s;
}

.back-btn:hover {
  color: #1d4ed8;
  border-color: #93c5fd;
  background: #eff6ff;
}

.loading-state {
  text-align: center;
  color: #64748b;
}

.terminated-banner,
.guest-banner {
  margin-bottom: 18px;
  padding: 18px 20px;
}

.terminated-banner {
  background: #fff7ed;
  color: #c2410c;
  border: 1px solid #fed7aa;
  border-radius: 18px;
  font-weight: 600;
}

.guest-banner {
  background: #f8fafc;
  color: #64748b;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
}

.team-panel-entry {
  margin-bottom: 14px;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
}

.team-panel-entry-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #334155;
}

.team-panel-entry-text strong {
  color: #0f172a;
}

.team-panel-entry-text span {
  font-size: 13px;
  color: #64748b;
}

.team-panel-open-btn {
  border: none;
  border-radius: 999px;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.22);
}

.team-required-hint {
  margin-bottom: 18px;
  padding: 18px 20px;
}

.team-required-hint h3 {
  margin: 0 0 8px;
  color: #0f172a;
}

.team-required-hint p {
  margin: 0;
  color: #64748b;
}

.team-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.team-modal-card {
  width: min(980px, 96vw);
  max-height: 90vh;
  overflow: auto;
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 28px 60px rgba(15, 23, 42, 0.26);
  padding: 18px;
}

.team-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.team-modal-header h3 {
  margin: 0;
  color: #0f172a;
}

.team-modal-close {
  border: none;
  background: #f1f5f9;
  color: #475569;
  width: 32px;
  height: 32px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
}

.pdf-upload-btn {
  border: none;
  border-radius: 999px;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  transition: transform 0.12s ease, box-shadow 0.2s ease, filter 0.2s ease;
}

.pdf-upload-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.pdf-upload-btn:disabled {
  cursor: not-allowed;
  box-shadow: none;
  opacity: 0.65;
}

.actions {
  margin-top: 24px;
  padding: 24px;
  border: 1px solid #e5ecf3;
  border-radius: 24px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.hint-text {
  font-size: 14px;
  color: #64748b;
}

.pdf-upload-panel {
  border: 1px solid #dbeafe;
  border-radius: 18px;
  padding: 16px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  display: grid;
  gap: 10px;
}

.pdf-upload-label {
  display: block;
  font-size: 13px;
  color: #475569;
  font-weight: 700;
}

.pdf-upload-input {
  font-size: 13px;
  border: 1px solid #dbe5f0;
  background: #fff;
  border-radius: 12px;
  padding: 10px;
}

.pdf-upload-input::file-selector-button {
  border: 0;
  border-radius: 8px;
  padding: 7px 12px;
  margin-right: 10px;
  cursor: pointer;
  background: #ecf5ff;
  color: #1d4ed8;
  font-weight: 700;
}

.pdf-upload-btn {
  justify-self: start;
  background: linear-gradient(135deg, #0f766e 0%, #0d9488 100%);
  color: #fff;
  box-shadow: 0 10px 24px rgba(13, 148, 136, 0.22);
}

.pdf-upload-status {
  font-size: 12px;
  color: #475569;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 8px 10px;
}

@media (max-width: 840px) {
  .problem-input-field {
    width: 88px;
    padding: 5px 8px;
    font-size: 0.86em;
  }

  .problem-container {
    padding: 0 14px 20px;
  }

  .nav-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .team-panel-entry {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>