<template>
  <div class="admin-container">
    <!-- Login Modal -->
    <div v-if="!isAuthenticated" class="login-overlay">
        <div class="login-box">
            <h2>🔐 管理员登录</h2>
            <input 
                type="password" 
                v-model="adminPassword" 
                placeholder="请输入管理员密码" 
                @keyup.enter="handleLogin"
                class="login-input"
            />
            <button @click="handleLogin" class="primary-btn full-width">进入管理端</button>
            <div v-if="loginError" class="error-msg">{{ loginError }}</div>
            <button @click="router.push('/')" class="back-link">返回首页</button>
        </div>
    </div>

    <!-- Main Content -->
    <div v-else class="main-content">
        <div class="header">
        <div class="brand">
            <h1>🎓 管理控制台</h1>
        </div>
        <div class="actions">
            <button class="logout-btn" @click="logout">退出登录</button>
        </div>
        </div>

        <div class="tabs-container">
             <div class="tab-item" :class="{active: activeTab === 'students'}" @click="switchTab('students')">学生管理</div>
             <div class="tab-item" :class="{active: activeTab === 'problems'}" @click="switchTab('problems')">题目管理</div>
             <div class="tab-item" :class="{active: activeTab === 'ranking'}" @click="switchTab('ranking')">总成绩排名</div>
             <div class="tab-item" :class="{active: activeTab === 'export'}" @click="switchTab('export')">数据导出</div>
             <div class="tab-item" :class="{active: activeTab === 'settings'}" @click="switchTab('settings')">系统设置</div>
        </div>

        <StudentManager 
            v-if="activeTab === 'students'" 
            :adminToken="adminToken" 
            @logout="logout"
        />

        <ProblemManager
            v-if="activeTab === 'problems'"
            :adminToken="adminToken"
            @logout="logout"
        />

        <TotalRanking
            v-if="activeTab === 'ranking'"
            :adminToken="adminToken"
            @logout="logout"
        />

        <ExportManager
            v-if="activeTab === 'export'"
            :adminToken="adminToken"
            @logout="logout"
        />

        <SystemSettings
            v-if="activeTab === 'settings'"
            :adminToken="adminToken"
            @logout="logout"
        />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

import StudentManager from '../components/admin/StudentManager.vue'
import ProblemManager from '../components/admin/ProblemManager.vue'
import TotalRanking from '../components/admin/TotalRanking.vue'
import ExportManager from '../components/admin/ExportManager.vue'
import SystemSettings from '../components/admin/SystemSettings.vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
const router = useRouter()

// Auth State
const isAuthenticated = ref(false)
const adminPassword = ref('')
const loginError = ref('')
const adminToken = ref(localStorage.getItem('adminToken') || '')

// Tabs
const activeTab = ref('students')

const switchTab = (tab) => {
    activeTab.value = tab
}

// Auth Logic
const handleLogin = async () => {
    loginError.value = ''
    try {
        const res = await axios.post(`${API_BASE_URL}/admin/login`, {
            password: adminPassword.value
        })
        adminToken.value = res.data.token
        localStorage.setItem('adminToken', adminToken.value)
        isAuthenticated.value = true
    } catch (e) {
        loginError.value = '密码错误'
    }
}

const logout = () => {
    localStorage.removeItem('adminToken')
    isAuthenticated.value = false
    adminToken.value = ''
}

onMounted(() => {
    // Check if we have token
    if (adminToken.value) {
        isAuthenticated.value = true
    }
})

</script>

<style scoped>
.admin-container {
  min-height: 100vh;
  background: #f0f2f5;
  font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  padding-bottom: 40px;
}

/* Header */
.header {
  background: #fff;
  padding: 0 40px;
  height: 64px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 1px 4px rgba(0,21,41,.08);
  margin-bottom: 24px;
}
.brand h1 {
  font-size: 20px;
  margin: 0;
  color: #1f2d3d;
}
.logout-btn {
    border: 1px solid #dcdfe6;
    background: transparent;
    color: #606266;
    padding: 6px 16px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.3s;
}
.logout-btn:hover {
    color: #409eff;
    border-color: #c6e2ff;
    background-color: #ecf5ff;
}

/* Tabs */
.tabs-container {
    display: flex;
    gap: 20px;
    padding: 0 40px;
    margin-bottom: 20px;
    border-bottom: 1px solid #ebeef5;
}
.tab-item {
    padding: 10px 10px;
    cursor: pointer;
    font-size: 15px;
    color: #606266;
    border-bottom: 3px solid transparent;
    transition: all 0.3s;
    margin-bottom: -1px;
}
.tab-item.active {
    color: #409eff;
    border-bottom-color: #409eff;
    font-weight: 600;
}
.tab-item:hover {
    color: #409eff;
}

/* Login Overlay */
.login-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: #f0f2f5;
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 100;
}
.login-box {
    background: white;
    padding: 40px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    width: 320px;
    text-align: center;
}
.login-box h2 {
    margin-top: 0;
    color: #303133;
    margin-bottom: 24px;
}
.login-input {
    width: 100%;
    padding: 10px;
    margin-bottom: 15px;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    box-sizing: border-box;
}
.full-width {
    width: 100%;
}
.primary-btn {
    background: #409eff;
    color: white;
    border: none;
    padding: 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    transition: background 0.3s;
}
.primary-btn:hover {
    background: #66b1ff;
}
.error-msg {
    margin-top: 15px;
    color: #f56c6c;
    font-size: 13px;
    background: #fef0f0;
    padding: 8px;
    border-radius: 4px;
}
.back-link {
    margin-top: 15px;
    background: none;
    border: none;
    color: #909399;
    cursor: pointer;
    font-size: 13px;
}
.back-link:hover {
    color: #606266;
    text-decoration: underline;
}
</style>
