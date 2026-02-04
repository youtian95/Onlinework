<template>
  <div class="page-container">
    <header class="nav-header">
        <div class="brand">
            <button @click="router.push('/problems')" class="back-btn">← 返回列表</button>
            <h1>总成绩排名</h1>
        </div>
        <div class="user-info">
            <span class="welcome">{{ studentId }}</span>
        </div>
    </header>

    <main class="main-content">
        <div class="content-card">
            <div v-if="loading" class="loading-state">
                <div class="spinner"></div>
                <p>正在加载排名数据...</p>
            </div>
            
            <div v-else class="ranking-table-wrapper">
                 <table class="ranking-table">
                    <thead>
                        <tr>
                            <th width="80">排名</th>
                            <th>姓名</th>
                            <th width="120">学号</th>
                            <th width="100" class="text-right">总得分</th>
                            <th width="100" class="text-right">得分率</th>
                            <th width="150" class="text-right">最后活跃</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="item in rankingList" :key="item.student_id" :class="{ 'my-rank': item.student_id === studentId }">
                            <td>
                                <span class="rank-badge" :class="'rank-' + item.rank">
                                    {{ item.rank }}
                                </span>
                            </td>
                            <td class="name-cell">{{ item.name }}</td>
                            <td class="sid-cell">{{ item.student_id }}</td>
                            <td class="score-cell">{{ item.score }}</td>
                            <td class="score-cell">{{ item.score_rate }}%</td>
                            <td class="time-cell">{{ formatDate(item.last_update) }}</td>
                        </tr>
                        <tr v-if="rankingList.length === 0">
                            <td colspan="6" class="empty-cell">暂无数据</td>
                        </tr>
                    </tbody>
                 </table>
            </div>
        </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const rankingList = ref([])
const loading = ref(true)
const studentId = localStorage.getItem('studentId')
const token = localStorage.getItem('studentToken')
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

const formatDate = (isoString) => {
    if (!isoString) return '-'
    const date = new Date(isoString)
    return date.toLocaleDateString()
}

onMounted(async () => {
    try {
        const res = await axios.get(`${API_BASE_URL}/problems/ranking`, {
            headers: { Authorization: `Bearer ${token}` }
        })
        rankingList.value = res.data
    } catch (e) {
        if (e.response && e.response.status === 401) {
            router.push('/')
        } else {
            console.error(e)
            alert("获取排名失败")
        }
    } finally {
        loading.value = false
    }
})
</script>

<style scoped>
.page-container {
    min-height: 100vh;
    background-color: #f5f7fa;
    display: flex;
    flex-direction: column;
}

.nav-header {
    background: white;
    padding: 1rem 2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 10;
}

.brand {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.brand h1 {
    font-size: 1.25rem;
    color: #2c3e50;
    margin: 0;
}

.back-btn {
    background: none;
    border: 1px solid #e2e8f0;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    color: #64748b;
    transition: all 0.2s;
}

.back-btn:hover {
    background: #f1f5f9;
    color: #334155;
    border-color: #cbd5e1;
}

.main-content {
    flex: 1;
    max-width: 1000px;
    margin: 2rem auto;
    width: 100%;
    padding: 0 1rem;
}

.content-card {
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    padding: 2rem;
    min-height: 400px;
}

.loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 0;
    color: #94a3b8;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid #e2e8f0;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1rem;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Table Styles - reusable from ProblemList logic ideally, but copied here for isolation */
.ranking-table {
    width: 100%;
    border-collapse: collapse;
}

.ranking-table th {
    text-align: left;
    padding: 12px 16px;
    color: #64748b;
    font-weight: 600;
    font-size: 0.9rem;
    border-bottom: 2px solid #e2e8f0;
}

.ranking-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #f1f5f9;
    color: #334155;
}

.text-right { text-align: right; }
.score-cell { 
    text-align: right; 
    font-weight: bold;
    color: #0f172a;
    font-feature-settings: "tnum";
}

.time-cell {
    text-align: right;
    color: #94a3b8;
    font-size: 0.85rem;
}

.rank-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #f1f5f9;
    color: #64748b;
    font-weight: bold;
    font-size: 0.85rem;
}

.rank-1 { background: #fef3c7; color: #d97706; }
.rank-2 { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; } /* Silver-ish */
.rank-3 { background: #ffedd5; color: #c2410c; } /* Bronze-ish */

.my-rank {
    background-color: #eff6ff;
}

.my-rank td {
    color: #1e40af;
    font-weight: 500;
}
</style>