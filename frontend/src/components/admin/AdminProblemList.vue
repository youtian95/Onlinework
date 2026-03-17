<template>
  <div>
    <div class="card list-section">
        <div class="card-header">
            <div class="header-left">
                <h3>题目列表 ({{ displayedProblems.length }})</h3>
                <label class="filter-check">
                    <input type="checkbox" v-model="showDeleted"> 🗑️ 显示回收站
                </label>
            </div>
            <button @click="fetchAdminProblems" class="refresh-btn">刷新列表</button>
        </div>
        
        <div class="table-container">
            <table v-if="displayedProblems.length > 0">
                <thead>
                    <tr>
                        <th width="120">题目ID</th>
                        <th>标题</th>
                        <th width="100">状态</th>
                        <th width="80">游客</th>
                        <th width="160">截止时间</th>
                        <th width="280">操作</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="p in displayedProblems" :key="p.id" :class="{ 'deleted-row': p.is_deleted }">
                        <td>{{ p.id }}</td>
                        <td>{{ p.title }}</td>
                        <td>
                            <span v-if="p.is_deleted" class="status-badge status-deleted">已删除</span>
                            <span v-else-if="!p.is_visible" class="status-badge status-draft">草稿</span>
                            <span v-else-if="isTerminated(p)" class="status-badge status-terminated">已截止</span>
                            <span v-else class="status-badge status-published">已发布</span>
                        </td>
                        <td>
                             <label class="toggle-switch" v-if="!p.is_deleted">
                                <input 
                                    type="checkbox" 
                                    :checked="p.is_public_view" 
                                    @change="toggleGuest(p)"
                                >
                                <span class="slider round"></span>
                            </label>
                            <span v-else>-</span>
                        </td>
                        <td>
                            <span v-if="p.deadline" class="deadline-text">{{ formatTime(p.deadline) }}</span>
                            <span v-else class="text-gray">-</span>
                        </td>
                        <td>
                            <div class="action-group">
                                <template v-if="!p.is_deleted">
                                    <button 
                                        @click="togglePublish(p)" 
                                        class="icon-btn" 
                                        :title="p.is_visible ? '取消发布' : '发布'"
                                    >
                                        {{ p.is_visible ? '🔒' : '📢' }}
                                    </button>
                                    
                                    <button @click="openDeadlineModal(p)" class="icon-btn" title="设置截止时间">
                                        ⏱️
                                    </button>
                                    
                                    <button 
                                        @click="toggleTerminate(p)" 
                                        class="icon-btn" 
                                        :title="isTerminated(p) ? '重新开放' : '立即截止'"
                                    >
                                        {{ isTerminated(p) ? '🔓' : '🛑' }}
                                    </button>

                                    <button @click="viewRanking(p)" class="icon-btn" title="查看排名">🏆</button>
                                    
                                    <button @click="deleteProblem(p)" class="icon-btn danger" title="删除">🗑️</button>
                                </template>
                                <template v-else>
                                    <button @click="restoreProblem(p)" class="action-btn success">♻️ 恢复</button>
                                </template>
                            </div>
                        </td>
                    </tr>
                </tbody>
            </table>
                <div v-else class="empty-text">暂无数据</div>
        </div>
    </div>

    <!-- Ranking Modal -->
    <div v-if="showRankingModal" class="modal-overlay" @click.self="closeRankingModal">
        <div class="modal-box" style="max-width: 600px;">
                <div class="modal-header">
                <h2>🏆 排行榜: {{ currentRankingProblem?.title }}</h2>
                <button class="close-btn" @click="closeRankingModal">×</button>
            </div>
                <div class="modal-content">
                <div v-if="rankingLoading" class="loading">加载中...</div>
                <div v-else-if="rankingData.length === 0" class="empty">暂无数据</div>
                <div v-else class="table-container">
                    <table class="ranking-table">
                        <thead>
                            <tr>
                                <th>排名</th>
                                <th>学号</th>
                                <th>姓名</th>
                                <th>得分</th>
                                <th>完成时间</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="item in rankingData" :key="item.student_id">
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
    </div>

    <!-- Deadline Modal -->
    <div v-if="editingDeadlineProblem" class="modal-overlay" @click.self="closeDeadlineModal">
        <div class="modal-box" style="max-width: 400px;">
            <div class="modal-header">
                <h2>📅 设置截止时间</h2>
                <button class="close-btn" @click="closeDeadlineModal">×</button>
            </div>
            <div class="modal-content">
                <div class="form-group" style="padding: 20px;">
                    <label style="display:block; margin-bottom: 10px;">选择截止时间:</label>
                    <input type="datetime-local" v-model="deadlineInput" class="text-input" style="width: 100%;" />
                    <div style="margin-top: 10px; color: #666; font-size: 12px;">留空则无截止时间</div>
                </div>
                <div class="modal-footer" style="padding: 0 20px 20px; text-align: right;">
                    <button @click="saveDeadline" class="primary-btn">保存</button>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const props = defineProps({
    adminToken: String
})

const emit = defineEmits(['logout'])

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// Problem Stats Data
const adminProblems = ref([])
const problemsLoading = ref(false)
const showRankingModal = ref(false)
const rankingData = ref([])
const rankingLoading = ref(false)
const currentRankingProblem = ref(null)

// Filters
const showDeleted = ref(false)
const displayedProblems = computed(() => {
    return adminProblems.value.filter(p => showDeleted.value ? (p.is_deleted) : (!p.is_deleted))
})

// Deadline Modal
const editingDeadlineProblem = ref(null)
const deadlineInput = ref('')

const isTerminated = (p) => {
    if (!p.deadline) return false
    return new Date(p.deadline) < new Date()
}

// Actions
const updateProblemState = async (problem, updates) => {
    try {
        const res = await axios.put(
            `${API_BASE_URL}/admin/problems/${problem.id}/state`, 
            updates,
            { headers: { 'X-Admin-Token': props.adminToken } }
        )
        // Merge result safely, preserving id (string) and title
        const newState = res.data
        problem.is_visible = newState.is_visible
        problem.is_deleted = newState.is_deleted
        problem.is_public_view = newState.is_public_view
        problem.deadline = newState.deadline
        // problem.id and problem.title are kept as is from the original list
        // because response id is database int id, and title might be null

    } catch (e) {
        if(e.response && e.response.status === 401) emit('logout')
        else alert('操作失败')
    }
}

const togglePublish = (p) => {
    updateProblemState(p, { is_visible: !p.is_visible })
}

const toggleGuest = (p) => {
    updateProblemState(p, { is_public_view: !p.is_public_view })
}

const toggleTerminate = (p) => {
    if (isTerminated(p)) {
        if (confirm(`确定要重新开放题目 ${p.id} 吗？`)) {
            updateProblemState(p, { deadline: null })
        }
        return
    }

    if (confirm(`确定要立即截止题目 ${p.id} 吗？`)) {
        updateProblemState(p, { deadline: new Date().toISOString() })
    }
}

const deleteProblem = (p) => {
    if (confirm(`确定要删除 ${p.id} 吗？删除后将进入回收站。`)) {
        updateProblemState(p, { is_deleted: true })
    }
}

const restoreProblem = (p) => {
    updateProblemState(p, { is_deleted: false })
}

const openDeadlineModal = (p) => {
    editingDeadlineProblem.value = p
    if (p.deadline) {
        const d = new Date(p.deadline)
        // Convert to local YYYY-MM-DDTHH:mm format manually to avoid timezone calculation errors
        const pad = (n) => n.toString().padStart(2, '0')
        const year = d.getFullYear()
        const month = pad(d.getMonth() + 1)
        const day = pad(d.getDate())
        const hours = pad(d.getHours())
        const minutes = pad(d.getMinutes())
        deadlineInput.value = `${year}-${month}-${day}T${hours}:${minutes}`
    } else {
        deadlineInput.value = ''
    }
}

const closeDeadlineModal = () => {
    editingDeadlineProblem.value = null
    deadlineInput.value = ''
}

const saveDeadline = () => {
    if (editingDeadlineProblem.value) {
        let isoDeadline = null
        if (deadlineInput.value) {
            isoDeadline = new Date(deadlineInput.value).toISOString()
        }
        updateProblemState(editingDeadlineProblem.value, { deadline: isoDeadline })
        closeDeadlineModal()
    }
}

const fetchAdminProblems = async () => {
    problemsLoading.value = true
    try {
        const res = await axios.get(`${API_BASE_URL}/admin/problems`, {
                headers: { 'X-Admin-Token': props.adminToken }
        })
        adminProblems.value = res.data
    } catch (e) {
        if(e.response && e.response.status === 401) emit('logout')
        else alert('加载题目列表失败')
    } finally {
        problemsLoading.value = false
    }
}

const viewRanking = async (problem) => {
    currentRankingProblem.value = problem
    showRankingModal.value = true
    rankingLoading.value = true
    rankingData.value = []
    
    try {
         const res = await axios.get(`${API_BASE_URL}/admin/problems/${problem.id}/ranking`, {
                headers: { 'X-Admin-Token': props.adminToken }
         })
         rankingData.value = res.data
    } catch (e) {
         alert('获取排名失败')
    } finally {
        rankingLoading.value = false
    }
}

const closeRankingModal = () => {
    showRankingModal.value = false
}

const formatTime = (isoString) => {
    if (!isoString) return '-'
    return new Date(isoString).toLocaleString()
}

onMounted(() => {
    if (adminProblems.value.length === 0) {
        fetchAdminProblems()
    }
})

// Expose fetch method to parent
defineExpose({
    fetchAdminProblems
})
</script>

<style scoped>
.card {
    background: #fff;
    border-radius: 8px;
    padding: 24px;
    box-shadow: 0 1px 2px -2px rgba(0,0,0,0.16), 0 3px 6px 0 rgba(0,0,0,0.12), 0 5px 12px 4px rgba(0,0,0,0.09);
    height: fit-content;
}
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}
h3 {
    margin: 0;
    color: #303133;
    font-size: 18px;
}
.refresh-btn {
    background: none;
    border: 1px solid #dcdfe6;
    padding: 5px 12px;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
    color: #606266;
    transition: all 0.3s;
}
.refresh-btn:hover {
    color: #409eff;
    border-color: #c6e2ff;
    background-color: #ecf5ff;
}
.table-container {
    overflow-x: auto;
}
table {
    width: 100%;
    border-collapse: collapse;
}
th, td {
    text-align: left;
    padding: 12px 16px;
    border-bottom: 1px solid #ebeef5;
    font-size: 14px;
}
th {
    color: #909399;
    font-weight: 500;
    background: #fafafa;
}
td {
    color: #606266;
}
tr:hover {
    background-color: #f5f7fa;
}
.empty-text {
    text-align: center;
    padding: 40px;
    color: #909399;
}
.action-btn {
    color: #409eff;
    background: #ecf5ff;
    border: 1px solid #b3d8ff;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.3s;
}
.action-btn:hover {
    background: #409eff;
    color: white;
}

/* New Status Badges */
.status-badge {
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 12px;
    border: 1px solid transparent;
}
.status-published { background: #f0f9eb; color: #67c23a; border-color: #e1f3d8; }
.status-draft { background: #f4f4f5; color: #909399; border-color: #e9e9eb; }
.status-terminated { background: #fdf6ec; color: #e6a23c; border-color: #faecd8; }
.status-deleted { background: #fef0f0; color: #f56c6c; border-color: #fde2e2; }

/* Header & Filter */
.header-left {
    display: flex;
    align-items: center;
    gap: 20px;
}
.filter-check {
    font-size: 14px;
    color: #606266;
    display: flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
}
.deleted-row {
    background-color: #fcfcfc;
    opacity: 0.8;
}

/* Action Group */
.action-group {
    display: flex;
    gap: 8px;
    align-items: center;
}
.icon-btn {
    background: none;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 14px;
    color: #606266;
    transition: all 0.2s;
    padding: 0;
}
.icon-btn:hover {
    color: #409eff;
    border-color: #c6e2ff;
    background-color: #ecf5ff;
}
.icon-btn.danger:hover {
    color: #f56c6c;
    border-color: #fde2e2;
    background-color: #fef0f0;
}
.deadline-text {
    font-size: 12px;
    color: #606266;
}
.text-gray {
    color: #ccc;
}

/* Modal Styles - Reuse or Global */
.modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 200;
}
.modal-box {
    background: white;
    width: 800px;
    max-width: 90%;
    max-height: 85vh;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 25px rgba(0,0,0,0.2);
}
.modal-header {
    padding: 20px;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.modal-header h2 {
    margin: 0;
    font-size: 18px;
    color: #303133;
}
.close-btn {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #909399;
}
.modal-content {
    padding: 20px;
    overflow-y: auto;
    background: #f5f7fa;
}

/* Ranking styles */
.rank-badge {
    display: inline-block;
    width: 24px; height: 24px; line-height: 24px;
    text-align: center; background: #f4f4f5; color: #909399;
    border-radius: 50%; font-size: 12px; font-weight: bold;
}
.rank-1 { background: #ffd700; color: #fff; }
.rank-2 { background: #c0c0c0; color: #fff; }
.rank-3 { background: #cd7f32; color: #fff; }
.score-cell { font-weight: bold; color: #67c23a; font-family: monospace; }
.time-cell { font-size: 12px; color: #999; }
</style>

.toggle-switch { position: relative; display: inline-block; width: 40px; height: 20px; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 20px; }
.slider:before { position: absolute; content: ''; height: 16px; width: 16px; left: 2px; bottom: 2px; background-color: white; transition: .4s; border-radius: 50%; }
input:checked + .slider { background-color: #2196F3; }
input:checked + .slider:before { transform: translateX(20px); }
