<template>
  <div class="page-container">
    <!-- 顶部导航 -->
    <StudentNavbar 
        :studentId="studentId" 
        @logout="logout"
    />
    
    <main class="main-content">
        <div class="content-card">
            <div class="card-header">
                <h2>我的作业列表</h2>
                <div class="header-actions">
                    <button class="rank-btn-main" @click="router.push('/ranking')">🏆 总成绩排名</button>
                    <span class="count" v-if="!loading">共 {{ problems.length }} 个任务</span>
                </div>
            </div>

            <div v-if="loading" class="loading-state">
                <div class="spinner"></div>
                <p>正在加载作业...</p>
            </div>

            <div v-else-if="problems.length === 0" class="empty-state">
                <span class="empty-icon">📭</span>
                <p>暂时没有发布的作业</p>
            </div>

            <ul v-else class="problem-list">
                <li v-for="problem in problems" :key="problem.id" @click="goToProblem(problem.id)" class="problem-item">
                    <div class="problem-info">
                        <span class="problem-id">{{ problem.id }}</span>
                        <div class="problem-detail-col">
                            <span class="problem-title">
                                {{ problem.title }}
                                <span v-if="problem.is_terminated" class="badge-terminated">已截止</span>
                            </span>
                            <div class="problem-meta">
                                <span class="problem-score" v-if="problem.total_score !== undefined">
                                    得分: {{ problem.obtained_score }} / {{ problem.total_score }}
                                </span>
                                <span class="problem-deadline" v-if="problem.deadline && !problem.is_terminated">
                                    截止: {{ new Date(problem.deadline).toLocaleString() }}
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="problem-action">
                         <span class="rank-btn" @click.stop="viewRanking(problem)">🏆 排名</span>
                        <span class="action-text">{{ problem.is_terminated ? '查看内容' : '开始作答' }}</span>
                        <span class="arrow">→</span>
                    </div>
                </li>
            </ul>
        </div>
    </main>

    <!-- Ranking Modal -->
    <ProblemRankingModal 
        v-if="showRankingModal"
        :problemId="currentRankingProblem?.id"
        :problemTitle="currentRankingProblem?.title"
        :studentId="studentId"
        @close="closeRankingModal"
    />

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import StudentNavbar from '../components/student/StudentNavbar.vue'
import ProblemRankingModal from '../components/student/ProblemRankingModal.vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

const problems = ref([])
const loading = ref(true)
const router = useRouter()
const studentId = localStorage.getItem('studentId')
const token = localStorage.getItem('studentToken')

// Ranking State
const showRankingModal = ref(false)
const currentRankingProblem = ref(null)

const viewRanking = (problem) => {
    currentRankingProblem.value = problem
    showRankingModal.value = true
}

const closeRankingModal = () => {
    showRankingModal.value = false
    currentRankingProblem.value = null
}

onMounted(async () => {
    if (!token) {
        router.push('/')
        return
    }
    try {
        // 不需要 check 接口，直接获取问题列表，后端会验证 Token
        const res = await axios.get(`${API_BASE_URL}/problems`, {
            headers: { Authorization: `Bearer ${token}` }
        })
        problems.value = res.data
    } catch (e) {
        if (e.response && e.response.status === 401) {
            alert('登录已过期')
            localStorage.removeItem('studentToken')
            router.push('/')
        } else {
             // alert('该学号未被授权进入系统')
        }
    } finally {
        loading.value = false
    }
})

const goToProblem = (id) => {
    router.push(`/problems/${id}`)
}

const logout = () => {
    localStorage.removeItem('studentId')
    localStorage.removeItem('studentToken')
    localStorage.removeItem('studentName')
    router.push('/')
}
</script>

<style scoped>
.page-container {
    min-height: 100vh;
    background-color: #f5f7fa;
    font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

/* Main Content */
.main-content {
    max-width: 900px;
    margin: 40px auto;
    padding: 0 20px;
}

.content-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    padding: 30px;
    min-height: 400px;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;
    padding-bottom: 15px;
    border-bottom: 2px solid #f0f2f5;
}
.card-header h2 {
    margin: 0;
    font-size: 20px;
    color: #303133;
}
.header-actions {
    display: flex;
    align-items: center;
    gap: 15px;
}
.rank-btn-main {
    background: #fff8e1;
    border: 1px solid #fcd34d;
    color: #b45309;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s;
}
.rank-btn-main:hover {
    background: #fef3c7;
    transform: translateY(-1px);
}
.count {
    font-size: 13px;
    color: #909399;
    background: #f4f4f5;
    padding: 4px 10px;
    border-radius: 12px;
}

/* List */
.problem-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.problem-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    background: #fff;
    border: 1px solid #ebeef5;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s ease;
}

.problem-item:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    border-color: #c6e2ff;
}

.problem-info {
    display: flex;
    align-items: center;
    gap: 15px;
}

.problem-id {
    font-size: 12px;
    font-weight: bold;
    color: #409eff;
    background: #ecf5ff;
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid #d9ecff;
}
.problem-detail-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.problem-score {
    font-size: 13px;
    color: #67c23a;
    font-weight: 500;
}

.problem-title {
    font-size: 16px;
    color: #303133;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
}
.badge-terminated {
    background: #fdf6ec;
    color: #e6a23c;
    border: 1px solid #faecd8;
    font-size: 11px;
    padding: 1px 5px;
    border-radius: 4px;
}
.problem-meta {
    display: flex;
    gap: 15px;
    font-size: 13px;
    color: #888;
}
.problem-deadline {
    color: #e6a23c;
}

.problem-action {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #909399;
    transition: color 0.3s;
}

.action-text {
    font-size: 13px;
    opacity: 0;
    transform: translateX(10px);
    transition: all 0.3s;
}

.problem-item:hover .action-text {
    opacity: 1;
    transform: translateX(0);
    color: #409eff;
}
.problem-item:hover .arrow {
    color: #409eff;
}

/* Rank Button */
.rank-btn {
    margin-right: 15px;
    font-size: 12px;
    padding: 4px 10px;
    background: #fff0f0;
    color: #f56c6c;
    border-radius: 4px;
    border: 1px solid #fde2e2;
    transition: all 0.2s;
    z-index: 2; /* 确保在点击事件中优先 */
    font-weight: 500;
}
.rank-btn:hover {
    background: #f56c6c;
    color: white;
}

/* Loading & Empty States */
.loading-state, .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 300px;
    color: #909399;
}

.spinner {
    width: 30px;
    height: 30px;
    border: 3px solid #ebeef5;
    border-top-color: #409eff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 20px;
}

.empty-icon {
    font-size: 48px;
    margin-bottom: 20px;
    opacity: 0.5;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

@media (max-width: 600px) {
    .problem-item {
        padding: 15px;
    }
    .action-text {
        display: none;
    }
    .problem-title {
        font-size: 15px;
    }
}
</style>
