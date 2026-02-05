<template>
  <div class="problem-container">
    <div class="nav-bar">
        <button @click="router.push('/problems')" class="back-btn">← 返回列表</button>
        <div class="nav-right">
             <span class="score-badge" v-if="totalScore > 0">当前得分: {{ currentScore }} / {{ totalScore }}</span>
             <span class="user-badge">{{ studentId }}</span>
        </div>
    </div>

    <div v-if="loading">加载题目中...</div>
    <div v-else>
        <!-- Terminated Banner -->
        <div v-if="isTerminated" class="terminated-banner">
             🛑 作业已截止 ({{ formatTime(deadline) }})，仅供查看，无法提交。
        </div>

        <!-- 题目动态渲染区域 -->
        <div class="problem-content markdown-body" v-html="renderedContent"></div>

        <div class="actions" v-if="!isTerminated">
            <!-- 整体提交按钮已废弃，改为单个输入框回车提交 -->
            <!-- <button class="submit-btn" @click="submitAnswers">提交答案</button> -->
             <div class="hint-text">💡 提示：输入答案后按 <b>Enter</b> 键提交单个空</div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { marked } from 'marked'
import markedKatex from 'marked-katex-extension'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// 引入 Katex 样式，实际项目中需要在 index.html 或全局 CSS 引入
// 这里假设已经在 index.html 引入或者忽略样式问题先跑通功能

// 使用 marked 的 KaTeX 插件处理公式
// strict: "ignore" 允许 \htmlId 等 HTML 扩展
marked.use(markedKatex({ throwOnError: false, trust: true, strict: 'ignore' }))

const route = useRoute()
const router = useRouter()
const studentId = localStorage.getItem('studentId')
const token = localStorage.getItem('studentToken')
const problemId = route.params.id

const loading = ref(true)
const rawContent = ref('')
const inputIds = ref([])
const renderedContent = ref('')
const userAnswers = ref({})
const result = ref(null)
const attemptStatus = ref({})
const meta = ref({})
const isTerminated = ref(false)
const deadline = ref(null)

const formatTime = (iso) => new Date(iso).toLocaleString()

const totalScore = computed(() => {
    if (!meta.value.inputs) return 0
    return Object.values(meta.value.inputs).reduce((sum, item) => sum + (item.score || 0), 0)
})

const currentScore = computed(() => {
    if (!meta.value.inputs) return 0
    let score = 0
    // attemptStatus key corresponds to input id
    for (const [id, status] of Object.entries(attemptStatus.value)) {
        if (status.correct) {
            const item = meta.value.inputs[id]
            score += (item?.score || 0)
        }
    }
    return score
})

// 前端组件化核心黑科技：
// 后端返回的是 <problem-input id="ans_1"></problem-input>
// 我们在 mounted 后，手动把这些 tag 替换成真的 input 框
// 并且绑定事件

onMounted(async () => {
    if (!token) {
        router.push('/')
        return
    }
    
    try {
        const res = await axios.get(`${API_BASE_URL}/problems/${problemId}`, {
            headers: { Authorization: `Bearer ${token}` }
        })
        const data = res.data
        
        // 1. 渲染 Markdown -> HTML (包含数学公式)
        let html = marked(data.content)

        rawContent.value = html
        inputIds.value = data.input_ids
        attemptStatus.value = data.attempt_status || {}
        meta.value = data.meta || {}
        isTerminated.value = data.is_terminated || false
        deadline.value = data.deadline
        
        // 2. 注入 HTML 并挂载 Inputs
        renderedContent.value = html
        
        // 先显示内容
        loading.value = false

        // 等待 DOM 更新后绑定 Input
        nextTick(() => {
            bindInputs() 
        })
        
    } catch (e) {
        console.error(e)
        if (e.response && e.response.status === 403) {
            alert('题目未发布或无权限访问')
            router.push('/problems')
        } else if (e.response && e.response.status === 404) {
            alert('题目不存在')
            router.push('/problems')
        } else {
             // alert('该学号未被授权进入系统') // Keep original error handling style or improve
             alert('加载题目失败:' + (e.response?.data?.detail || e.message))
        }
    } finally {
        loading.value = false
    }
})

// 绑定自定义标签为真实输入框，并实现双向绑定
const bindInputs = () => {
    inputIds.value.forEach(id => {
        const ph = document.getElementById(id)
        if (!ph) return
        const status = attemptStatus.value[id] || { remaining: 0, locked: false, correct: false }
        
        // 创建真实 Input
        const input = document.createElement('input')
        input.type = 'text'
        input.className = 'problem-input-field'
        
        // Logic for disabled state
        const isLocallyLocked = status.locked || status.correct
        const isGloballyLocked = isTerminated.value
        
        if (isGloballyLocked) {
             input.placeholder = '已截止'
             input.disabled = true
             input.classList.add('terminated')
        } else if (status.correct) {
             input.placeholder = '已正确'
             input.disabled = true
        } else if (status.locked) {
             input.placeholder = '已锁定'
             input.disabled = true
        } else {
             input.placeholder = '请输入答案'
             input.disabled = false
        }
        
        // 双向绑定逻辑 (模拟 v-model)
        input.value = userAnswers.value[id] || ''
        input.oninput = (e) => {
            userAnswers.value[id] = e.target.value
        }
        
        // 绑定回车事件
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                submitSingleAnswer(id)
            }
        })
        
        // 保存 ID 到 dataset 以便后续查找
        input.dataset.id = id

        // 状态提示
        const info = document.createElement('span')
        info.className = 'attempt-info'
        info.dataset.id = id
        info.textContent = status.correct
            ? '已正确'
            : (status.locked ? '已锁定' : `剩余 ${status.remaining} 次`)

        // 包装并替换 DOM
        const wrapper = document.createElement('span')
        wrapper.className = 'input-wrapper'
        wrapper.appendChild(input)
        wrapper.appendChild(info)
        ph.replaceWith(wrapper)
    })
}

// 根据尝试状态更新输入框状态
const applyAttemptStatusToInputs = (statusMap) => {
    const inputs = document.querySelectorAll('.problem-input-field')
    inputs.forEach(input => {
        const id = input.dataset.id
        const status = statusMap[id]
        if (!status) return

        input.disabled = status.locked || status.correct
        input.placeholder = status.locked ? '已锁定' : '请输入答案'

        const info = document.querySelector(`.attempt-info[data-id="${id}"]`)
        if (info) {
            info.textContent = status.correct
                ? '已正确'
                : (status.locked ? '已锁定' : `剩余 ${status.remaining} 次`)
        }
    })
}

// 提交单个答案
const submitSingleAnswer = async (input_id) => {
    // 构建只包含该 ID 的答案对象
    const singleAnswer = {}
    singleAnswer[input_id] = userAnswers.value[input_id]

    try {
        const res = await axios.post(`${API_BASE_URL}/problems/submit`, {
            problem_id: problemId,
            answers: singleAnswer 
        }, {
            headers: { Authorization: `Bearer ${token}` }
        })
        
        // 更新尝试状态（后端会返回所有 ID 的最新状态）
        attemptStatus.value = res.data.attempt_status || {}
        
        // 更新 UI 样式
        // 注意：后端返回的 results 可能包含所有字段的校验结果，但我们只关心当前这一个
        const isCorrect = res.data.results[input_id]
        updateInputStyle(input_id, isCorrect)
        
        applyAttemptStatusToInputs(attemptStatus.value)

    } catch (e) {
         if (e.response && (e.response.status === 403 || e.response.status === 401)) {
            alert('登录已过期或未授权')
            localStorage.removeItem('studentToken')
            router.push('/')
        } else {
            console.error(e)
            // 简单的抖动错误反馈，或者 toast
        }
    }
}

const updateInputStyle = (id, isCorrect) => {
    const input = document.querySelector(`.problem-input-field[data-id="${id}"]`)
    if (!input) return
    
    if (isCorrect === true) {
        input.style.borderColor = '#67c23a'
        input.style.backgroundColor = '#f0f9eb'
        input.blur() // 正确后失去焦点
    } else if (isCorrect === false) {
        input.style.borderColor = '#f56c6c'
        input.style.backgroundColor = '#fef0f0'
        // 错误时保持焦点方便修改，或者添加抖动动画
    }
}

// 废弃旧的批量提交函数，或者保留用于"一键提交所有"（如果有的话）
// const submitAnswers = ... 
</script>

<style>
/* 全局样式，因为 v-html 里的内容不受 scoped 控制 */
.markdown-body {
    line-height: 1.8;
    font-size: 16px;
    color: #333;
}
.markdown-body p {
    margin-bottom: 1em;
}
.problem-input-field {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 6px 10px;
    margin: 0 4px;
    width: 100px; 
    font-family: inherit;
    font-size: 0.95em;
    text-align: center;
    transition: all 0.3s;
    background: #fff;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.problem-input-field:focus {
    border-color: #409eff;
    outline: none;
    box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}
.problem-input-field:disabled {
    background-color: #f5f7fa;
    color: #909399;
    cursor: not-allowed;
}
.input-wrapper {
    display: inline-flex;
    position: relative; /* 设置相对定位，作为 tooltip 的容器 */
    vertical-align: middle;
    align-items: center;
    margin: 0 4px;
}
/* 悬浮提示样式 (Tooltip) */
.attempt-info {
    position: absolute;
    top: 110%; /* 显示在输入框下方 */
    left: 50%;
    transform: translateX(-50%);
    background-color: rgba(0, 0, 0, 0.8);
    color: #fff;
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 12px;
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s, top 0.2s;
    z-index: 100;
}

/* 小箭头 (指向下方的内容，所以箭头在上面指向下...不对，Tooltip在下方，箭头应在Top指向上) */
.attempt-info::after {
    content: '';
    position: absolute;
    bottom: 100%; /* 箭头位于 Tooltip 顶部 */
    left: 50%;
    margin-left: -5px;
    border-width: 5px;
    border-style: solid;
    border-color: transparent transparent rgba(0, 0, 0, 0.8) transparent;
}

.input-wrapper:hover .attempt-info {
    opacity: 1;
    top: 125%; /* 悬浮时效果 */
}

/* KaTeX 公式间距微调 */
.katex-display {
    margin: 0.5em 0 !important; /* 减小上下间距 */
    padding: 2px 0;
}
</style>

<style scoped>
.terminated-banner {
    background: #fdf6ec;
    color: #e6a23c;
    border: 1px solid #faecd8;
    padding: 10px 15px;
    margin-bottom: 20px;
    border-radius: 4px;
    font-weight: 500;
}

.problem-container {
    max-width: 900px;
    margin: 40px auto;
    padding: 30px;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.nav-bar {
    margin-bottom: 30px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #ebeef5;
    padding-bottom: 15px;
}

.nav-right {
    display: flex;
    align-items: center;
    gap: 15px;
}

.score-badge {
    font-weight: bold;
    color: #67c23a;
    background: #f0f9eb;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 14px;
}

.user-badge {
    font-weight: 500;
    color: #303133;
}

.nav-bar button {
    background: none;
    border: none;
    color: #606266;
    cursor: pointer;
    font-size: 15px;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: color 0.2s;
}

.nav-bar button:hover {
    color: #409eff;
}

.nav-bar span {
    font-weight: 500;
    color: #303133;
}

.result-box {
    margin-top: 25px;
    padding: 16px;
    border-radius: 6px;
    font-weight: 600;
    text-align: center;
    animation: fadeIn 0.3s ease-out;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
}

.result-box.success {
    background-color: #f0f9eb;
    color: #67c23a;
    border: 1px solid #e1f3d8;
}

.result-box.error {
    background-color: #fef0f0;
    color: #f56c6c;
    border: 1px solid #fde2e2;
}

.actions {
    margin-top: 30px;
    border-top: 1px solid #ebeef5;
    padding-top: 20px;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
}

.submit-btn {
    background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
    color: white;
    border: none;
    padding: 12px 30px;
    border-radius: 20px;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    box-shadow: 0 4px 10px rgba(64, 158, 255, 0.3);
    transition: transform 0.1s, box-shadow 0.2s;
}

.submit-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 15px rgba(64, 158, 255, 0.4);
}

.hint-text {
    font-size: 14px;
    color: #909399;
    padding: 10px;
    text-align: right;
}
</style>
