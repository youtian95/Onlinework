<template>
  <div class="modal-overlay" @click.self="$emit('close')">
        <div class="modal-card">
            <div class="modal-header">
                <div>
                    <h3>🏆 {{ problemTitle }} - 排行榜</h3>
                    <div v-if="teamworkEnabled" class="scope-switch">
                        <button
                            type="button"
                            class="scope-btn"
                            :class="{ active: scope === 'personal' }"
                            @click="changeScope('personal')"
                        >
                            个人榜
                        </button>
                        <button
                            type="button"
                            class="scope-btn"
                            :class="{ active: scope === 'team' }"
                            @click="changeScope('team')"
                        >
                            队伍榜
                        </button>
                    </div>
                </div>
                <button class="close-btn" @click="$emit('close')">×</button>
            </div>
            <div class="modal-body">
                <div v-if="loading" class="loading-state-mini">
                    加载中...
                </div>
                <div v-else-if="rankingData.length === 0" class="empty-state-mini">
                    暂无数据
                </div>
                <table v-else class="ranking-table">
                    <thead v-if="isTeamScope">
                        <tr>
                            <th>名次</th>
                            <th>队伍</th>
                            <th>人数</th>
                            <th>得分</th>
                            <th>得分率</th>
                            <th>最后更新</th>
                        </tr>
                    </thead>
                    <thead v-else-if="teamworkEnabled">
                        <tr>
                            <th>名次</th>
                            <th>学号</th>
                            <th>姓名</th>
                            <th>队伍</th>
                            <th>认领</th>
                            <th>得分</th>
                            <th>得分率</th>
                            <th>最后更新</th>
                        </tr>
                    </thead>
                    <thead v-else>
                        <tr>
                            <th>名次</th>
                            <th>学号</th>
                            <th>姓名</th>
                            <th>得分</th>
                            <th>最后更新</th>
                        </tr>
                    </thead>
                    <tbody v-if="isTeamScope">
                        <tr v-for="item in rankingData" :key="item.team_id" :class="{ 'is-me': isMyTeam(item) }">
                            <td>
                                <span class="rank-badge" :class="'rank-' + item.rank">{{ item.rank }}</span>
                            </td>
                            <td>
                                <div class="team-cell">
                                    <strong>{{ item.team_name || `第 ${item.team_no} 队` }}</strong>
                                    <span class="team-sub">第 {{ item.team_no }} 队</span>
                                </div>
                            </td>
                            <td>{{ item.member_count }}</td>
                            <td class="score-cell">{{ item.score }} / {{ item.total_possible }}</td>
                            <td class="score-cell">{{ item.score_rate }}%</td>
                            <td class="time-cell">{{ formatTime(item.last_update) }}</td>
                        </tr>
                    </tbody>
                    <tbody v-else-if="teamworkEnabled">
                        <tr v-for="item in rankingData" :key="item.student_id" :class="{ 'is-me': item.student_id === studentId }">
                            <td>
                                <span class="rank-badge" :class="'rank-' + item.rank">{{ item.rank }}</span>
                            </td>
                            <td>{{ item.student_id }}</td>
                            <td>{{ item.name }}</td>
                            <td>{{ item.team_no ? `第 ${item.team_no} 队` : '-' }}</td>
                            <td>{{ item.subproblem_no ? `子题 ${item.subproblem_no}` : '-' }}</td>
                            <td class="score-cell">{{ item.score }} / {{ item.total_possible }}</td>
                            <td class="score-cell">{{ item.score_rate }}%</td>
                            <td class="time-cell">{{ formatTime(item.last_update) }}</td>
                        </tr>
                    </tbody>
                    <tbody v-else>
                        <tr v-for="item in rankingData" :key="item.student_id" :class="{ 'is-me': item.student_id === studentId }">
                            <td>
                                <span class="rank-badge" :class="'rank-' + item.rank">{{ item.rank }}</span>
                            </td>
                            <td>{{ item.student_id }}</td>
                            <td>{{ item.name }}</td>
                            <td class="score-cell">{{ item.score }}</td>
                            <td class="time-cell">{{ formatTime(item.last_update) }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { computed } from 'vue'

const props = defineProps({
    problemId: [String, Number],
    problemTitle: String,
    studentId: String,
    teamworkEnabled: Boolean
})

const emit = defineEmits(['close'])

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
const rankingData = ref([])
const loading = ref(true)
const scope = ref('personal')

const isTeamScope = computed(() => props.teamworkEnabled && scope.value === 'team')

const myTeamNo = computed(() => {
    const problemKey = String(props.problemId || '')
    const raw = localStorage.getItem('problemTeamMemberships')
    if (!raw) return null
    try {
        const parsed = JSON.parse(raw)
        return parsed?.[problemKey]?.team_no ?? null
    } catch {
        return null
    }
})

const formatTime = (isoString) => {
    if (!isoString) return '-'
    return new Date(isoString).toLocaleString()
}

const isMyTeam = (item) => myTeamNo.value !== null && item.team_no === myTeamNo.value

const fetchRanking = async () => {
    loading.value = true
    try {
        const token = localStorage.getItem('studentToken')
        const params = {}
        if (props.teamworkEnabled) {
            params.scope = scope.value
        }
        const res = await axios.get(`${API_BASE_URL}/problems/${props.problemId}/ranking`, {
            headers: { Authorization: `Bearer ${token}` },
            params,
        })
        rankingData.value = res.data
    } catch (e) {
        alert('获取排名失败')
    } finally {
        loading.value = false
    }
}

const changeScope = (nextScope) => {
    if (!props.teamworkEnabled || scope.value === nextScope) {
        return
    }
    scope.value = nextScope
    fetchRanking()
}

onMounted(async () => {
    await fetchRanking()
})
</script>

<style scoped>
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.2s;
}

.modal-card {
    background: #fff;
    width: 800px;
    max-width: 90%;
    max-height: 80vh;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}

.modal-header {
    padding: 20px;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
}
.modal-header h3 { margin: 0; font-size: 18px; color: #303133; }

.scope-switch {
    display: inline-flex;
    gap: 8px;
    margin-top: 12px;
    padding: 4px;
    background: #f6f7fb;
    border-radius: 999px;
}

.scope-btn {
    border: none;
    background: transparent;
    color: #6b7280;
    padding: 7px 12px;
    border-radius: 999px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
}

.scope-btn.active {
    background: #ffffff;
    color: #1d4ed8;
    box-shadow: 0 2px 10px rgba(29, 78, 216, 0.12);
}

.close-btn {
    background: none; border: none; font-size: 24px; cursor: pointer; color: #999;
}
.close-btn:hover { color: #333; }

.modal-body {
    padding: 20px;
    overflow-y: auto;
}

.ranking-table {
    width: 100%;
    border-collapse: collapse;
}
.ranking-table th {
    text-align: left;
    color: #909399;
    font-weight: normal;
    padding: 10px;
    border-bottom: 2px solid #f0f2f5;
    font-size: 13px;
}
.ranking-table td {
    padding: 12px 10px;
    border-bottom: 1px solid #f0f2f5;
    color: #606266;
    font-size: 14px;
}

.is-me {
    background-color: #f0f9eb;
}
.is-me td { color: #67c23a; font-weight: bold; }

.rank-badge {
    display: inline-block;
    width: 24px;
    height: 24px;
    line-height: 24px;
    text-align: center;
    background: #f4f4f5;
    color: #909399;
    border-radius: 50%;
    font-size: 12px;
    font-weight: bold;
}
.rank-1 { background: #ffd700; color: #fff; }
.rank-2 { background: #c0c0c0; color: #fff; }
.rank-3 { background: #cd7f32; color: #fff; }

.score-cell { font-family: 'Consolas', monospace; font-weight: bold; }
.time-cell { font-size: 12px; color: #999; }
.team-cell {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.team-sub {
    font-size: 12px;
    color: #94a3b8;
}

.loading-state-mini { text-align: center; padding: 40px; color: #999; }
.empty-state-mini { text-align: center; padding: 40px; color: #ccc; }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>