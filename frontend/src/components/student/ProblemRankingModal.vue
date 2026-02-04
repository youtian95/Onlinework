<template>
  <div class="modal-overlay" @click.self="$emit('close')">
        <div class="modal-card">
            <div class="modal-header">
                <h3>🏆 {{ problemTitle }} - 排行榜</h3>
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
                    <thead>
                        <tr>
                            <th>名次</th>
                            <th>学号</th>
                            <th>姓名</th>
                            <th>得分</th>
                            <th>完成时间</th>
                        </tr>
                    </thead>
                    <tbody>
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

const props = defineProps({
    problemId: [String, Number],
    problemTitle: String,
    studentId: String
})

const emit = defineEmits(['close'])

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
const rankingData = ref([])
const loading = ref(true)

const formatTime = (isoString) => {
    if (!isoString) return '-'
    return new Date(isoString).toLocaleDateString()
}

onMounted(async () => {
    loading.value = true
    try {
        const token = localStorage.getItem('studentToken')
        const res = await axios.get(`${API_BASE_URL}/problems/${props.problemId}/ranking`, {
            headers: { Authorization: `Bearer ${token}` }
        })
        rankingData.value = res.data
    } catch (e) {
        alert('获取排名失败')
    } finally {
        loading.value = false
    }
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
    width: 600px;
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
}
.modal-header h3 { margin: 0; font-size: 18px; color: #303133; }

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
.loading-state-mini { text-align: center; padding: 40px; color: #999; }
.empty-state-mini { text-align: center; padding: 40px; color: #ccc; }

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>