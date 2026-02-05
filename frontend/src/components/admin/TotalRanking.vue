<template>
    <div class="content-wrapper full-width-layout">
        <div class="card list-section">
             <div class="card-header">
                <h3>平台总成绩排名</h3>
                <button @click="fetchTotalRanking" class="refresh-btn">刷新</button>
            </div>
             <div class="table-container">
                 <table v-if="totalRanking.length > 0">
                    <thead>
                        <tr>
                            <th width="80">排名</th>
                            <th>姓名</th>
                            <th>学号</th>
                            <th class="text-right" width="100">总得分</th>
                            <th class="text-right" width="100">得分率</th>
                            <th class="text-right" width="150">最近活跃</th>
                        </tr>
                    </thead>
                    <tbody>
                         <tr v-for="item in totalRanking" :key="item.student_id">
                             <td><span class="rank-badge" :class="'rank-'+item.rank">{{ item.rank }}</span></td>
                             <td>{{ item.name }}</td>
                             <td>{{ item.student_id }}</td>
                             <td class="text-right"><strong>{{ item.score }}</strong></td>
                             <td class="text-right">{{ item.score_rate }}%</td>
                             <td class="text-right">{{ formatDate(item.last_update) }}</td>
                         </tr>
                    </tbody>
                 </table>
                  <div v-else-if="rankingLoading" class="loading-text">加载中...</div>
                  <div v-else class="empty-text">暂无排名数据</div>
             </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

const totalRanking = ref([])
const rankingLoading = ref(false)

const formatDate = (isoString) => {
    if (!isoString) return '-'
    const date = new Date(isoString)
    return date.toLocaleDateString()
}

const fetchTotalRanking = async () => {
    rankingLoading.value = true
    try {
        const res = await axios.get(`${API_BASE_URL}/admin/ranking`, {
            headers: { Authorization: `Bearer ${localStorage.getItem('adminToken')}` }
        })
        totalRanking.value = res.data
    } catch (e) {
        console.error(e)
    } finally {
        rankingLoading.value = false
    }
}

onMounted(() => {
    fetchTotalRanking()
})
</script>

<style scoped>
.content-wrapper {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
}
.full-width-layout {
    display: block;
}
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
.loading-text {
    text-align: center;
    padding: 20px;
    color: #909399;
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
.text-right { text-align: right; }
</style>