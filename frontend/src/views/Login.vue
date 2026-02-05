<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>🎓 {{ systemName }}</h1>
        <p v-if="!setupRequired">欢迎登录在线作业系统</p>
        <p v-else>首次登录，请设置您的密码</p>
      </div>

      <div class="step-content">
          <div class="form-group">
            <label>学号</label>
            <input 
                v-model="studentId" 
                placeholder="请输入你的学号" 
                class="login-input"
                @input="resetSetupState"
                autofocus
            />
          </div>

          <div class="form-group">
            <label>密码</label>
            <input 
                type="password"
                v-model="password" 
                placeholder="请输入密码" 
                class="login-input"
                @keyup.enter="handleMainAction"
            />
          </div>

          <transition name="fade">
            <div class="form-group" v-if="setupRequired">
                <label>确认密码</label>
                <input 
                    type="password"
                    v-model="confirmPassword" 
                    placeholder="请再次输入密码" 
                    class="login-input"
                    @keyup.enter="handleMainAction"
                    ref="confirmPwdInput"
                />
            </div>
          </transition>

          <button @click="handleMainAction" :disabled="loading" class="primary-btn">
             <span v-if="loading">处理中...</span>
             <span v-else>{{ setupRequired ? '确认设置并登录' : '登录' }}</span>
          </button>
      </div>

      <div v-if="errorMessage" class="error-msg">
          {{ errorMessage }}
      </div>

      <div class="footer-links">
        <span @click="router.push('/admin')" class="link-text">我是管理员</span>
        <span v-if="setupRequired" @click="resetSetupState" class="link-text" style="margin-left: 15px;">返回登录</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')

// Data
const studentId = ref('')
const password = ref('')
const confirmPassword = ref('')
const setupRequired = ref(false)
const confirmPwdInput = ref(null)

const resetSetupState = () => {
    setupRequired.value = false
    confirmPassword.value = ''
    errorMessage.value = ''
}

const handleMainAction = async () => {
    errorMessage.value = ''
    if (!studentId.value.trim()) {
        errorMessage.value = '请输入学号'
        return
    }
    if (!password.value) {
        errorMessage.value = '请输入密码'
        return
    }

    if (setupRequired.value) {
        // Handle Setup
        await handleSetup()
    } else {
        // Handle Login Check -> Login
        await checkAndLogin()
    }
}

const checkAndLogin = async () => {
    loading.value = true
    try {
        const res = await axios.get(`${API_BASE_URL}/auth/check?student_id=${studentId.value}`)
        const status = res.data.status // 'login_required' | 'setup_required'
        
        if (status === 'setup_required') {
            setupRequired.value = true
            errorMessage.value = '检测到您是首次登录，请再次输入密码以设置。'
            loading.value = false
            nextTick(() => {
                if(confirmPwdInput.value) confirmPwdInput.value.focus()
            })
        } else {
            // login_required -> Proceed to login
            await performLogin()
        }
    } catch (e) {
        loading.value = false
        if (e.response && e.response.status === 404) {
            errorMessage.value = '未找到该学号，请联系管理员添加白名单'
        } else if (e.response && e.response.status === 403) {
            errorMessage.value = '该账号已被禁用'
        } else {
            errorMessage.value = '网络错误，请稍后重试'
        }
    }
}

const performLogin = async () => {
    try {
        const res = await axios.post(`${API_BASE_URL}/auth/login`, {
            student_id: studentId.value,
            password: password.value
        })
        const { access_token, name } = res.data;
        localStorage.setItem('studentToken', access_token)
        localStorage.setItem('studentId', studentId.value)
        localStorage.setItem('studentName', name)
        router.push('/problems')
    } catch (e) {
        errorMessage.value = '密码错误，请重试'
    } finally {
        loading.value = false
    }
}

const handleSetup = async () => {
    if (password.value !== confirmPassword.value) {
        errorMessage.value = '两次输入的密码不一致'
        return
    }
    
    loading.value = true
    try {
        await axios.post(`${API_BASE_URL}/auth/setup`, {
            student_id: studentId.value,
            password: password.value
        })
        // Login immediately after setup
        await performLogin()
    } catch (e) {
        errorMessage.value = e.response?.data?.detail || '设置失败'
        loading.value = false
    }
}

// System Settings
const systemName = ref('在线作业系统')
const bgStyle = ref({})

const fetchSystemSettings = async () => {
    try {
        const res = await axios.get(`${API_BASE_URL}/system/settings`)
        if (res.data.course_name) systemName.value = res.data.course_name
        if (res.data.cover_image) {
            const url = res.data.cover_image.startsWith('http') 
                ? res.data.cover_image 
                : `${API_BASE_URL}${res.data.cover_image}`
            
            // bgStyle.value = { background: `url(${url}) no-repeat center center fixed`, backgroundSize: 'cover' }
            // Better to apply to container
            const container = document.querySelector('.login-container')
            if(container) {
                container.style.background = `url(${url}) no-repeat center center fixed`
                container.style.backgroundSize = 'cover'
            }
        }
    } catch (e) {
        // ignore
    }
}

onMounted(() => {
    fetchSystemSettings()
})
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  transition: background 0.5s ease;
}

.login-card {
  background: white;
  width: 100%;
  max-width: 400px;
  padding: 40px;
  border-radius: 16px;
  box-shadow: 0 10px 25px rgba(0,0,0,0.1);
  text-align: center;
}

.login-header h1 {
  margin: 0 0 10px;
  font-size: 24px;
  color: #2c3e50;
  white-space: pre-wrap;
}

.login-header p {
  margin: 0 0 30px;
  color: #7f8c8d;
  font-size: 14px;
}

.form-group {
    text-align: left;
    margin-bottom: 20px;
}

.form-group label {
    display: block;
    margin-bottom: 8px;
    color: #34495e;
    font-weight: 500;
    font-size: 14px;
}

.login-input {
    width: 100%;
    padding: 12px;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-size: 16px;
    transition: all 0.3s;
    box-sizing: border-box; 
}

.login-input:focus {
    border-color: #42b983;
    outline: none;
    box-shadow: 0 0 0 3px rgba(66, 185, 131, 0.1);
}

.primary-btn {
    width: 100%;
    padding: 12px;
    background: #42b983;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.3s, transform 0.1s;
    margin-top: 10px;
}

.primary-btn:hover {
    background: #3aa876;
}

.primary-btn:active {
    transform: translateY(1px);
}

.primary-btn:disabled {
    background: #a8d5c2;
    cursor: not-allowed;
}

.error-msg {
    margin-top: 20px;
    color: #e74c3c;
    font-size: 14px;
    background: #fde8e7;
    padding: 10px;
    border-radius: 6px;
}

.footer-links {
    margin-top: 30px;
    border-top: 1px solid #eee;
    padding-top: 15px;
}

.link-text {
    color: #95a5a6;
    font-size: 13px;
    cursor: pointer;
}
.link-text:hover {
    color: #42b983;
    text-decoration: underline;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
