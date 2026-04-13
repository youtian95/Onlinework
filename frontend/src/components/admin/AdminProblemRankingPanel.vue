<template>
  <section class="card side-card">
    <template v-if="teamworkEnabled">
      <div class="panel-block">
        <div class="card-title-row">
          <h2>小组排名与成员</h2>
          <span class="meta-text">{{ teamworkConfig.team_count }} 组 / 每组 {{ teamworkConfig.team_size }} 人</span>
        </div>

        <div class="config-row">
          <div class="config-field">
            <label for="team-count-input">队伍数量</label>
            <input id="team-count-input" v-model="teamCountDraft" type="number" min="1" class="count-input" />
          </div>
          <div class="config-field fixed-field">
            <label>每队人数</label>
            <div class="fixed-value">{{ teamworkConfig.team_size }}</div>
          </div>
          <button type="button" class="save-btn" :disabled="savingTeamConfig || !canSaveTeamCount" @click="saveTeamCount">
            {{ savingTeamConfig ? '保存中...' : '保存数量' }}
          </button>
        </div>
        <div class="config-note">团队作业创建后只允许修改队伍数量，人数固定不变。</div>

        <div class="selector-row">
          <label for="team-select">查看小组:</label>
          <select id="team-select" :value="selectedTeamId ?? ''" @change="emitTeamChange($event)">
            <option v-for="team in teamRows" :key="team.team_id" :value="team.team_id">
              {{ team.name || `第${team.team_no}队` }}
            </option>
          </select>
        </div>

        <div class="rank-summary" v-if="selectedTeamId">
          <template v-if="selectedTeam && selectedTeam.rank">
            当前小组排名: <strong>第 {{ selectedTeam.rank }} 名</strong>
          </template>
          <template v-else>
            当前小组暂未上榜
          </template>
        </div>

        <div class="team-table-wrapper">
          <table class="team-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>队伍</th>
                <th>状态</th>
                <th>得分</th>
                <th>得分率</th>
                <th>成员</th>
                <th>最后更新</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="team in teamRows"
                :key="team.team_id"
                :class="{ 'selected-row': team.team_id === selectedTeamId }"
              >
                <td>
                  <span class="rank-badge" :class="`rank-${team.rank}`">{{ team.rank || '-' }}</span>
                </td>
                <td><strong>{{ team.name || `第${team.team_no}队` }}</strong></td>
                <td>
                  <span class="status-pill" :class="progressClass(team)">
                    {{ progressText(team) }}
                  </span>
                </td>
                <td>{{ team.score }} / {{ team.total_possible }}</td>
                <td>{{ team.score_rate }}%</td>
                <td>{{ team.member_count }} / {{ team.max_members }}</td>
                <td>{{ formatTime(team.last_update) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <article class="member-card" v-if="selectedTeam">
          <div class="member-card-header">
            <strong>{{ selectedTeam.name || `第${selectedTeam.team_no}队` }}</strong>
            <span>{{ selectedTeam.member_count }} 人</span>
          </div>

          <ul v-if="selectedTeam.members.length" class="member-list">
            <li v-for="member in selectedTeam.members" 
                :key="`${selectedTeam.team_id}-${member.student_id}`"
                :class="{ 'selected-member': member.student_id === selectedStudentId }"
                @click="emitStudentChange(member.student_id)">
              <div class="member-info">
                <span class="member-name">{{ member.name || member.student_id }}</span>
                <span class="member-id">{{ member.student_id }}</span>
              </div>
              <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
                <span class="claim-chip">
                  {{ member.claimed_subproblem ? `认领子题 ${member.claimed_subproblem}` : '未认领' }}
                </span>
                <a v-if="member.pdf_path" :href="`${API_BASE_URL}/admin/submission-download?pdf_path=${encodeURIComponent(member.pdf_path)}&token=${encodeURIComponent(props.adminToken || '')}`" class="download-link" style="font-size: 11px;">📥 ZIP</a>
                <span v-else class="empty-data" style="font-size: 11px;">无PDF</span>
              </div>
            </li>
          </ul>
          <div v-else class="empty-members">暂无成员</div>
        </article>
      </div>

      <div class="panel-block">
        <div class="card-title-row">
          <h2>个人排名</h2>
        </div>
        <div class="team-table-wrapper">
          <table class="team-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>学号</th>
                <th>姓名</th>
                <th>队伍</th>
                <th>认领子题</th>
                <th>得分</th>
                <th>得分率</th>
                <th>PDF文件</th>
                <th>最后更新</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rankingRows" :key="`team-personal-${row.student_id}`">
                <td>{{ row.rank }}</td>
                <td>{{ row.student_id }}</td>
                <td>{{ row.name || '-' }}</td>
                <td>{{ row.team_no ? `第${row.team_no}队` : '-' }}</td>
                <td>{{ row.subproblem_no ? `子题 ${row.subproblem_no}` : '未认领' }}</td>
                <td>{{ row.score }} / {{ row.total_possible }}</td>
                <td>{{ row.score_rate }}%</td>
                <td>
                  <a v-if="row.pdf_path" :href="`${API_BASE_URL}/admin/submission-download?pdf_path=${encodeURIComponent(row.pdf_path)}&token=${encodeURIComponent(props.adminToken || '')}`" class="download-link">📥 下载ZIP</a>
                  <span v-else class="empty-data">未上传</span>
                </td>
                <td>{{ formatTime(row.last_update) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="card-title-row">
        <h2>学生排名与目标选择</h2>
        <span class="meta-text">右侧排名将随题目实时更新</span>
      </div>

      <div class="selector-row">
        <label for="student-select">查看学生:</label>
        <select id="student-select" :value="selectedStudentId" @change="emitStudentChange($event)">
          <option v-for="student in studentOptions" :key="student.student_id" :value="student.student_id">
            {{ student.name || student.student_id }} ({{ student.student_id }})
          </option>
        </select>
      </div>

      <div class="rank-summary" v-if="selectedStudentId">
        <template v-if="selectedStudentRank">
          当前学生排名: <strong>第 {{ selectedStudentRank.rank }} 名</strong>
        </template>
        <template v-else>
          当前学生暂未上榜
        </template>
      </div>

      <div class="team-table-wrapper">
        <table class="team-table">
          <thead>
            <tr>
              <th>排名</th>
              <th>学号</th>
              <th>姓名</th>
              <th>得分</th>
              <th>PDF文件</th>
              <th>最后更新</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rankingRows"
              :key="row.student_id"
              :class="{ 'selected-row': row.student_id === selectedStudentId }"
            >
              <td>{{ row.rank }}</td>
              <td>{{ row.student_id }}</td>
              <td>{{ row.name || '-' }}</td>
              <td>{{ row.score }}</td>
              <td>
                <a v-if="row.pdf_path" :href="`${API_BASE_URL}/admin/submission-download?pdf_path=${encodeURIComponent(row.pdf_path)}&token=${encodeURIComponent(props.adminToken || '')}`" class="download-link">📥 下载ZIP</a>
                <span v-else class="empty-data">未上传</span>
              </td>
              <td>{{ formatTime(row.last_update) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

const props = defineProps({
  teamworkEnabled: {
    type: Boolean,
    default: false,
  },
  teamworkConfig: {
    type: Object,
    default: null,
  },
  teamRows: {
    type: Array,
    default: () => [],
  },
  selectedTeamId: {
    type: Number,
    default: null,
  },
  selectedTeam: {
    type: Object,
    default: null,
  },
  rankingRows: {
    type: Array,
    default: () => [],
  },
  studentOptions: {
    type: Array,
    default: () => [],
  },
  selectedStudentId: {
    type: String,
    default: '',
  },
  selectedStudentRank: {
    type: Object,
    default: null,
  },
  progressText: {
    type: Function,
    required: true,
  },
  progressClass: {
    type: Function,
    required: true,
  },
  formatTime: {
    type: Function,
    required: true,
  },
  savingTeamConfig: {
    type: Boolean,
    default: false,
  },
  adminToken: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:selectedTeamId', 'update:selectedStudentId', 'save:teamCount'])

const teamCountDraft = ref('')

watch(
  () => props.teamworkConfig?.team_count,
  (nextValue) => {
    teamCountDraft.value = nextValue == null ? '' : String(nextValue)
  },
  { immediate: true }
)

const canSaveTeamCount = computed(() => {
  if (!props.teamworkEnabled || !props.teamworkConfig) return false
  const nextValue = Number(teamCountDraft.value)
  if (!Number.isInteger(nextValue) || nextValue <= 0) return false
  return nextValue !== Number(props.teamworkConfig.team_count)
})

const emitTeamChange = (event) => {
  const raw = event?.target?.value
  emit('update:selectedTeamId', raw === '' ? null : Number(raw))
}

const emitStudentChange = (payload) => {
  const value = payload?.target !== undefined ? payload.target.value : payload
  emit('update:selectedStudentId', value || '')
}

const saveTeamCount = () => {
  const nextValue = Number(teamCountDraft.value)
  if (!Number.isInteger(nextValue) || nextValue <= 0) {
    return
  }
  emit('save:teamCount', nextValue)
}
</script>

<style scoped>
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

.meta-text {
  color: #6b7280;
  font-size: 13px;
}

.config-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 10px;
  align-items: end;
  margin-bottom: 10px;
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-field label {
  font-size: 13px;
  color: #334155;
}

.count-input,
.fixed-value {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  min-height: 38px;
  padding: 8px 10px;
  background: #fff;
  color: #0f172a;
  box-sizing: border-box;
}

.fixed-field .fixed-value {
  background: #f8fafc;
}

.save-btn {
  border: none;
  border-radius: 8px;
  min-height: 38px;
  padding: 0 14px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
}

.save-btn:disabled {
  background: #93c5fd;
  cursor: not-allowed;
}

.config-note {
  margin-bottom: 12px;
  font-size: 12px;
  color: #64748b;
}

.selector-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.selector-row label {
  font-size: 13px;
  color: #334155;
}

.selector-row select {
  flex: 1;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 7px 10px;
  background: #fff;
}

.rank-summary {
  margin-bottom: 12px;
  color: #334155;
  font-size: 13px;
  padding: 9px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.team-table-wrapper {
  overflow-x: auto;
  margin-bottom: 16px;
}

.team-table {
  width: 100%;
  border-collapse: collapse;
}

.team-table th,
.team-table td {
  padding: 10px;
  border-bottom: 1px solid #edf2f7;
  font-size: 13px;
  text-align: left;
}

.team-table th {
  color: #64748b;
  background: #f8fafc;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 6px;
  border-radius: 999px;
  background: #e5e7eb;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}

.rank-1 {
  background: #fbbf24;
  color: #fff;
}

.rank-2 {
  background: #94a3b8;
  color: #fff;
}

.rank-3 {
  background: #c2410c;
  color: #fff;
}

.selected-row {
  background: #eef6ff;
}

.status-pill {
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid transparent;
}

.status-pill.done {
  color: #166534;
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.status-pill.active {
  color: #1d4ed8;
  background: #eff6ff;
  border-color: #bfdbfe;
}

.status-pill.idle {
  color: #475569;
  background: #f8fafc;
  border-color: #e2e8f0;
}

.member-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
  padding: 12px;
}

.member-card-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #1f2937;
}

.member-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 8px;
}

.member-list li {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 8px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  transition: all 0.2s ease;
}

.member-list li:hover {
  border-color: #3b82f6;
  background: #eff6ff;
}

.member-list li.selected-member {
  border-color: #2563eb;
  background: #e0f2fe;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.member-info {
  display: flex;
  flex-direction: column;
}

.member-name {
  display: block;
  color: #111827;
  font-size: 13px;
}

.member-id {
  color: #64748b;
  font-size: 12px;
}

.claim-chip {
  align-self: center;
  border-radius: 999px;
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1e40af;
  font-size: 12px;
  padding: 4px 8px;
  white-space: nowrap;
}

.empty-members {
  text-align: center;
  padding: 24px;
  color: #64748b;
}

.panel-block + .panel-block {
  margin-top: 18px;
}

@media (max-width: 720px) {
  .config-row {
    grid-template-columns: 1fr;
  }

  .member-list li {
    flex-direction: column;
    align-items: flex-start;
  }

  .selector-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
