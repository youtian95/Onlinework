<template>
  <section class="teamwork-panel">
    <div class="teamwork-summary card-shell">
      <div>
        <p class="eyebrow">团队作业</p>
        <h2>{{ teamJoined ? `当前在 ${currentTeamLabel}` : '请先加入一个队伍' }}</h2>
        <p class="summary-text" v-if="teamConfig">
          共 {{ teamConfig.team_count }} 队，每队 {{ teamConfig.team_size }} 人，对应 {{ teamConfig.subproblem_count }} 个子问题区域。
        </p>
        <p class="summary-text" v-if="teamJoined && myClaimSubproblem">
          你当前认领的是子题 {{ myClaimSubproblem }}，默认已展开该区域。
        </p>
        <p class="summary-text" v-else-if="teamJoined">
          你还没有认领子题。认领后才能编辑对应区域中的输入框。
        </p>
      </div>
      <div class="summary-side">
        <span class="summary-pill" :class="teamJoined ? 'ok' : 'warn'">
          {{ teamJoined ? '已入队' : '待入队' }}
        </span>
        <span v-if="myClaimSubproblem" class="summary-pill accent">子题 {{ myClaimSubproblem }}</span>
      </div>
    </div>

    <div v-if="teamRows.length" class="team-grid">
      <article
        v-for="team in teamRows"
        :key="team.team_id"
        class="team-card card-shell"
        :class="{ active: teamInfo?.team_no === team.team_no }"
      >
        <div class="team-card-header">
          <div>
            <h3>{{ team.name || `第 ${team.team_no} 队` }}</h3>
            <p>人数 {{ team.member_count }} / {{ team.max_members }}</p>
          </div>
          <button
            type="button"
            class="team-action-btn"
            :disabled="isTeamActionDisabled(team)"
            @click="$emit('join-team', team.team_no)"
          >
            {{ getTeamActionText(team) }}
          </button>
        </div>

        <ul v-if="team.members.length" class="member-list">
          <li v-for="member in team.members" :key="member.student_id">
            <strong>{{ member.name || member.student_id }}</strong>
            <span>{{ member.student_id }}</span>
          </li>
        </ul>
        <div v-else class="empty-team">当前还没有成员</div>
      </article>
    </div>
  </section>

</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  teamJoined: {
    type: Boolean,
    default: false,
  },
  teamInfo: {
    type: Object,
    default: null,
  },
  teamConfig: {
    type: Object,
    default: null,
  },
  teamRows: {
    type: Array,
    default: () => [],
  },
  myClaimSubproblem: {
    type: Number,
    default: null,
  },
})

defineEmits(['join-team'])

const currentTeamLabel = computed(() => {
  if (!props.teamInfo) return ''
  if (props.teamInfo.team_name) return props.teamInfo.team_name
  if (props.teamInfo.team_no) return `第 ${props.teamInfo.team_no} 队`
  return '已入队'
})

const getTeamActionText = (team) => {
  if (props.teamInfo?.team_no === team.team_no) return '当前队伍'
  if (team.member_count >= team.max_members) return '已满'
  if (props.teamJoined) return '切换到此队'
  return '加入此队'
}

const isTeamActionDisabled = (team) => {
  if (props.teamInfo?.team_no === team.team_no) return true
  return team.member_count >= team.max_members
}
</script>

<style scoped>
.card-shell {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, #ffffff 100%);
  border: 1px solid #e5ecf3;
  border-radius: 24px;
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.06);
}

.teamwork-panel {
  display: grid;
  gap: 18px;
  margin-bottom: 20px;
}

.teamwork-summary {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #2563eb;
  text-transform: uppercase;
}

.teamwork-summary h2 {
  margin: 0;
  font-size: 26px;
  color: #0f172a;
}

.summary-text {
  margin: 10px 0 0;
  color: #475569;
  line-height: 1.7;
}

.summary-side {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-content: flex-start;
  gap: 10px;
  min-width: 180px;
}

.summary-pill {
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 13px;
  font-weight: 600;
}

.summary-pill.ok {
  color: #166534;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}

.summary-pill.warn {
  color: #9a3412;
  background: #fff7ed;
  border: 1px solid #fed7aa;
}

.summary-pill.accent {
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.team-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.team-card {
  padding: 20px;
}

.team-card.active {
  border-color: #93c5fd;
  box-shadow: 0 20px 40px rgba(37, 99, 235, 0.12);
}

.team-card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.team-card-header h3 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.team-card-header p {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.team-action-btn {
  border: none;
  border-radius: 999px;
  padding: 10px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.22);
  transition: transform 0.12s ease, box-shadow 0.2s ease, filter 0.2s ease;
}

.team-action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.team-action-btn:disabled {
  cursor: not-allowed;
  box-shadow: none;
  opacity: 0.65;
}

.member-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 10px;
}

.member-list li {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  color: #334155;
}

.empty-team {
  text-align: center;
  color: #64748b;
}

@media (max-width: 840px) {
  .teamwork-summary,
  .team-card-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .summary-side {
    justify-content: flex-start;
    min-width: 0;
  }
}
</style>
