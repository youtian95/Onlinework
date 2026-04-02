<template>
  <div>
    <div class="tabs-container">
        <button 
            class="tab-btn" 
            :class="{active: activeTab === 'students'}" 
            @click="activeTab = 'students'">
            👤 学生管理
        </button>
        <button 
            class="tab-btn" 
            :class="{active: activeTab === 'archives'}" 
            @click="activeTab = 'archives'">
            📦 学期归档
        </button>
    </div>

    <!-- == STUDENTS TAB == -->
    <div v-show="activeTab === 'students'" class="content-wrapper student-wrapper-layout">
        
        <!-- Upload Card -->
        <div class="card upload-section">
            <h3>批量导入学生</h3>
            <p class="subtitle">支持 CSV 文件，列名格式：student_id, name, enabled</p>
            
            <div class="upload-area">
            <label class="file-input-label">
                <span class="icon">📂</span>
                <span class="text" v-if="!file">点击选择文件</span>
                <span class="text" v-else>{{ file.name }}</span>
                <input type="file" accept=".csv" @change="handleFileChange" hidden />
            </label>
            <button :disabled="!file || loading" @click="uploadFile" class="primary-btn">
                {{ loading ? '上传中...' : '开始导入' }}
            </button>
            </div>
            
            <div v-if="errorMessage" class="error-msg">{{ errorMessage }}</div>

            <transition name="fade">
                <div v-if="result" class="result-box">
                    <div class="stat-item success">
                        <span class="num">{{ result.inserted }}</span>
                        <span class="label">新增</span>
                    </div>
                    <div class="stat-item warning">
                        <span class="num">{{ result.updated }}</span>
                        <span class="label">更新</span>
                    </div>
                    <div class="stat-item error">
                        <span class="num">{{ result.errors }}</span>
                        <span class="label">失败</span>
                    </div>
                </div>
            </transition>
        </div>

        <!-- Student List Card -->
        <div class="card list-section">
            <div class="card-header">
                <h3>{{ showDeleted ? '回收站 (已删除学生)' : `学生列表 (${students.length})` }}</h3>
                <div class="header-actions">
                    <button @click="toggleDeletedView" class="secondary-btn small" :class="{active: showDeleted}" style="margin-right: 10px;">
                        {{ showDeleted ? '返回列表' : '回收站' }}
                    </button>
                    <button v-if="!showDeleted" @click="openCreateModal" class="primary-btn small" style="margin-right: 10px;">+ 新增账号</button>
                    <button @click="fetchStudents" class="refresh-btn">刷新列表</button>
                </div>
            </div>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>学号</th>
                            <th>姓名</th>
                            <th>类型</th>
                            <th>状态</th>
                            <th>密码状态</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="s in students" :key="s.id">
                            <td>{{ s.id }}</td>
                            <td>{{ s.student_id }}</td>
                            <td>{{ s.name || '-' }}</td>
                            <td>
                                <span 
                                    class="badge clickable" 
                                    :class="s.is_test ? 'yellow' : 'blue'"
                                    @click="toggleTestAccount(s)"
                                    title="点击切换账户类型"
                                >
                                    {{ s.is_test ? '测试账号' : '正式账号' }}
                                </span>
                            </td>
                            <td>
                                <span class="badge" :class="s.enabled ? 'green' : 'red'">
                                    {{ s.enabled ? '正常' : '禁用' }}
                                </span>
                            </td>
                            <td>
                                <span class="status-text" :class="s.password_hash ? 'set' : 'unset'">
                                    {{ s.password_hash ? '已设置' : '未设置' }}
                                </span>
                            </td>
                            <td>
                                <button v-if="!showDeleted" @click="openStudentDetail(s)" class="action-btn" style="margin-right: 5px;">查看进度</button>
                                <button v-if="!showDeleted" @click="deleteStudent(s)" class="action-btn danger">删除</button>
                                <button v-else @click="restoreStudent(s)" class="action-btn success">恢复账号</button>
                            </td>
                        </tr>
                        <tr v-if="students.length === 0">
                            <td colspan="7" class="empty-text">{{ showDeleted ? '回收站为空' : '暂无数据，请先导入' }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- == ARCHIVES TAB == -->
    <div v-show="activeTab === 'archives'" class="content-wrapper">
        <div class="card" style="margin-bottom: 20px; border-left: 5px solid #E6A23C;">
            <h3>📤 新建归档 (本学期结束)</h3>
            <p class="subtitle">此操作会将当前数据库（学生名单、作业提交记录）打包保存到服务器，并<b>清空数据库</b>以便开始新学期。</p>
            
            <div class="archive-form">
                <div class="form-group">
                    <label>归档班级名称 (例如: 2023_Fall_CS101)</label>
                    <div style="display: flex; gap: 10px;">
                        <input v-model="archiveName" class="text-input" placeholder="输入名称..." style="max-width: 300px;" />
                        <button @click="createArchive" class="warning-btn" :disabled="!archiveName || archiving">
                            {{ archiving ? '归档中...' : '确认归档并清空数据' }}
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>📜 历史归档</h3>
                <button @click="fetchArchives" class="refresh-btn">刷新</button>
            </div>
            
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>文件名</th>
                            <th>创建时间</th>
                            <th>大小</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="arc in archives" :key="arc.filename">
                            <td>{{ arc.filename }}</td>
                            <td>{{ formatTime(arc.created_at) }}</td>
                            <td>{{ (arc.size / 1024 / 1024).toFixed(2) }} MB</td>
                            <td>
                                <button @click="restoreArchiveInTable(arc.filename)" class="action-btn" style="margin-right: 10px;">恢复此归档</button>
                                <button @click="deleteArchive(arc.filename)" class="action-btn danger">删除</button>
                            </td>
                        </tr>
                        <tr v-if="archives.length === 0">
                            <td colspan="4" class="empty-text">暂无归档记录</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Create Student Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="closeCreateModal">
        <div class="modal-box" style="max-width: 400px;">
            <div class="modal-header">
                <h2>👤 新增账号</h2>
                <button class="close-btn" @click="closeCreateModal">×</button>
            </div>
            <div class="modal-content">
                <div class="form-group">
                    <label>学号 *</label>
                    <input v-model="createForm.student_id" class="text-input" placeholder="唯一标识" />
                </div>
                <div class="form-group">
                    <label>姓名</label>
                    <input v-model="createForm.name" class="text-input" placeholder="学生姓名" />
                </div>
                <div class="form-group">
                    <label>密码</label>
                    <input v-model="createForm.password" class="text-input" type="password" placeholder="留空则需学生自行设置" />
                </div>
                 <div class="form-group row">
                    <label>测试账号</label>
                    <input type="checkbox" v-model="createForm.is_test" />
                    <span class="hint">测试账号不参与总排名</span>
                </div>
                
                <div v-if="createError" class="error-msg">{{ createError }}</div>
                
                <div class="modal-footer">
                    <button @click="createStudent" :disabled="creating" class="primary-btn">
                        {{ creating ? '创建中...' : '确认创建' }}
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- Detail Modal -->
    <div v-if="showDetailModal" class="modal-overlay" @click.self="closeDetail">
        <div class="modal-box">
            <div class="modal-header">
                <h2>📊 学习进度: {{ selectedStudent?.name }} ({{ selectedStudent?.student_id }})</h2>
                <button class="close-btn" @click="closeDetail">×</button>
            </div>
            
            <div class="modal-content">
                <div v-if="loadingProgress" class="loading">加载中...</div>
                <div v-else-if="progressData.length === 0" class="empty">暂无题目数据</div>
                
                <div v-else class="progress-list">
                    <div v-for="p in progressData" :key="p.id" class="progress-item">
                        <div class="prob-header">
                              <div class="prob-info">
                                  <span class="prob-title">{{ p.title }}</span>
                                  <span class="prob-id">{{ p.id }}</span>
                              </div>
                              <div class="prob-pdf-status">
                                  <a v-if="p.pdf_path" :href="`${API_BASE_URL.replace('/api', '')}/public/${p.pdf_path}`" target="_blank" class="pdf-download-link">📥 下载PDF</a>
                                  <span v-else class="pdf-not-uploaded">未上传PDF</span>
                              </div>
                          </div>

                        <div class="input-table-wrapper">
                            <table class="input-table">
                                <thead>
                                    <tr>
                                        <th>填空ID</th>
                                        <th>状态</th>
                                        <th>已用尝试 / 上限</th>
                                        <th>操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr v-for="(info, inputId) in p.inputs" :key="inputId">
                                        <td>{{ inputId }}</td>
                                        <td>
                                            <span class="badge" :class="info.correct ? 'green' : (info.attempts >= info.max_attempts ? 'red' : 'gray')">
                                                {{ info.correct ? '已正确' : (info.attempts >= info.max_attempts ? '已锁定' : '进行中') }}
                                            </span>
                                        </td>
                                        <td>
                                            <div class="attempt-edit">
                                                <input 
                                                    type="number" 
                                                    v-model.number="info.attempts" 
                                                    min="0"
                                                    class="tiny-input"
                                                />
                                                <span class="divider">/</span>
                                                <span class="max-val">{{ info.max_attempts }}</span>
                                            </div>
                                        </td>
                                        <td>
                                            <button @click="saveAttempts(p.id, inputId, info)" class="save-btn">保存修改</button>
                                             <button @click="resetAttempts(p.id, inputId, info)" class="reset-btn" title="重置为0并设为未完成">↺</button>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'

const props = defineProps({
    adminToken: String
})

const emit = defineEmits(['logout'])

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// == Tabs ==
const activeTab = ref('students')

// == Student State ==
const students = ref([])
const loading = ref(false)
const file = ref(null)
const result = ref(null)
const errorMessage = ref('')
const showDeleted = ref(false)

// == Archive State ==
const archives = ref([])
const archiveName = ref('')
const archiving = ref(false)

// Fetch Logic
const fetchStudents = async () => {
    try {
        const res = await axios.get(`${API_BASE_URL}/admin/students`, {
            params: { deleted_only: showDeleted.value },
            headers: { 'X-Admin-Token': props.adminToken }
        })
        students.value = res.data
    } catch (e) {
        if (e.response && e.response.status === 401) {
            emit('logout')
        } else {
            console.error('Failed to fetch students', e)
        }
    }
}

const fetchArchives = async () => {
    try {
        const res = await axios.get(`${API_BASE_URL}/admin/export/archives`, {
            params: { token: props.adminToken }
        })
        archives.value = res.data
    } catch (e) {
        console.error("Fetch archives failed", e)
    }
}

// Watch tab switch
watch(activeTab, (val) => {
    if (val === 'students') fetchStudents()
    if (val === 'archives') fetchArchives()
})

// == Archive Logic ==

const createArchive = async () => {
    if(!archiveName.value) return
    if (!confirm(`确定要归档当前学期为 "${archiveName.value}" 吗？\n\n警告：当前数据库中的所有学生和作业记录将被清空！`)) {
        return
    }
    
    archiving.value = true
    try {
        await axios.post(`${API_BASE_URL}/admin/export/archives`, {
            name: archiveName.value
        }, {
             params: { token: props.adminToken }
        })
        alert("归档成功！数据库已清空。")
        archiveName.value = ''
        fetchArchives()
    } catch (e) {
        alert("归档失败: " + (e.response?.data?.detail || e.message))
    } finally {
        archiving.value = false
    }
}

const restoreArchiveInTable = async (filename) => {
    if (!confirm(`确定要从归档 "${filename}" 恢复数据吗？\n\n警告：当前的数据库将被覆盖！`)) return
    
    try {
        await axios.post(`${API_BASE_URL}/admin/export/archives/restore/${filename}`, null, {
            params: { token: props.adminToken }
        })
        alert("恢复成功！")
        // No need to switch tab automatically, user might want to check logs or something
    } catch (e) {
        alert("恢复失败: " + (e.response?.data?.detail || e.message))
    }
}

const deleteArchive = async (filename) => {
    if (!confirm(`确定要删除归档文件 "${filename}" 吗？此操作不可撤销。`)) return
    
    try {
        await axios.delete(`${API_BASE_URL}/admin/export/archives/${filename}`, {
            params: { token: props.adminToken }
        })
        fetchArchives()
    } catch (e) {
        alert("删除失败: " + (e.response?.data?.detail || e.message))
    }
}

const formatTime = (iso) => {
    return new Date(iso).toLocaleString()
}

// == Student Actions (Existing) ==

const toggleDeletedView = () => {
    showDeleted.value = !showDeleted.value
    fetchStudents()
}

const deleteStudent = async (s) => {
    if (!confirm(`确定要将 ${s.name || s.student_id} 移入回收站吗？\n该用户将无法登录。`)) return
    try {
        await axios.delete(`${API_BASE_URL}/admin/students/${s.student_id}`, {
             headers: { 'X-Admin-Token': props.adminToken }
        })
        fetchStudents()
    } catch(e) { 
        if(e.response?.status === 401) emit('logout')
        else alert('删除失败')
    }
}

const restoreStudent = async (s) => {
    if (!confirm(`确定要恢复 ${s.name || s.student_id} 吗？`)) return
    try {
        await axios.put(`${API_BASE_URL}/admin/students/${s.student_id}`, 
        { is_deleted: false },
        { headers: { 'X-Admin-Token': props.adminToken } })
        fetchStudents()
    } catch(e) { 
        if(e.response?.status === 401) emit('logout')
        else alert('恢复失败')
    }
}

// Create Student Modal logic
const showCreateModal = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = ref({
    student_id: '',
    name: '',
    password: '',
    is_test: false
})

const openCreateModal = () => {
    createForm.value = { student_id: '', name: '', password: '', is_test: false }
    createError.value = ''
    showCreateModal.value = true
}

const closeCreateModal = () => {
    showCreateModal.value = false
}

const createStudent = async () => {
    if (!createForm.value.student_id) {
        createError.value = '请输入学号'
        return
    }
    creating.value = true
    createError.value = ''
    try {
        await axios.post(`${API_BASE_URL}/admin/students`, createForm.value, {
            headers: { 'X-Admin-Token': props.adminToken }
        })
        fetchStudents()
        closeCreateModal()
    } catch (e) {
         if (e.response?.status === 401) {
             emit('logout') 
         } else {
             createError.value = e.response?.data?.detail || '创建失败'
         }
    } finally {
        creating.value = false
    }
}

const toggleTestAccount = async (s) => {
    const newState = !s.is_test
    if (!confirm(`确定要将用户 ${s.name} (${s.student_id}) 切换为${newState ? '测试账号' : '正式账号'}吗？\n${newState ? '测试账号将不会出现在排行榜中。' : '正式账号将参与排名。'}`)) {
        return
    }
    try {
        await axios.put(`${API_BASE_URL}/admin/students/${s.student_id}`, 
            { is_test: newState },
            { headers: { 'X-Admin-Token': props.adminToken } }
        )
        s.is_test = newState
    } catch (e) {
        if (e.response?.status === 401) emit('logout') 
        else alert('操作失败')
    }
}

const handleFileChange = (e) => {
  result.value = null
  errorMessage.value = ''
  const files = e.target.files
  file.value = files && files.length ? files[0] : null
}

const uploadFile = async () => {
  if (!file.value) return
  loading.value = true
  errorMessage.value = ''
  result.value = null
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    const res = await axios.post(`${API_BASE_URL}/admin/students/upload`, formData, {
      headers: { 
          'Content-Type': 'multipart/form-data',
          'X-Admin-Token': props.adminToken 
      }
    })
    result.value = res.data
    fetchStudents()
  } catch (e) {
      if (e.response?.status === 401) {
          emit('logout') 
      } else {
        errorMessage.value = e.response?.data?.detail || '上传失败，请检查文件格式'
      }
  } finally {
    loading.value = false
  }
}

// Progress Logic
const showDetailModal = ref(false)
const selectedStudent = ref(null)
const progressData = ref([])
const loadingProgress = ref(false)

const openStudentDetail = async (student) => {
    selectedStudent.value = student
    showDetailModal.value = true
    fetchProgress(student.student_id)
}

const closeDetail = () => {
    showDetailModal.value = false
    selectedStudent.value = null
    progressData.value = []
}

const fetchProgress = async (studentId) => {
    loadingProgress.value = true
    try {
        const res = await axios.get(`${API_BASE_URL}/admin/students/${studentId}/progress`, {
             headers: { 'X-Admin-Token': props.adminToken }
        })
        progressData.value = res.data
    } catch (e) {
        if (e.response?.status === 401) emit('logout')
        else alert("获取进度失败")
    } finally {
        loadingProgress.value = false
    }
}

const saveAttempts = async (problemId, inputId, info) => {
    try {
        await axios.post(`${API_BASE_URL}/admin/attempts/update`, {
            student_id: selectedStudent.value.student_id,
            problem_id: problemId,
            input_id: inputId,
            attempts: info.attempts,
            correct: info.correct 
        }, {
             headers: { 'X-Admin-Token': props.adminToken }
        })
        alert('修改成功')
    } catch (e) {
        alert('修改失败')
    }
}

const resetAttempts = async (problemId, inputId, info) => {
    if(!confirm('确定要重置该题尝试次数为0吗？状态将变为"未完成"。')) return
    
    info.attempts = 0
    info.correct = false
    saveAttempts(problemId, inputId, info)
}

onMounted(() => {
    fetchStudents()
})
</script>

<style scoped>
.content-wrapper {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
}

/* Tabs */
.tabs-container {
    max-width: 1200px;
    margin: 20px auto 20px;
    padding: 0 20px;
    display: flex;
    gap: 10px;
}

.tab-btn {
    padding: 10px 20px;
    font-size: 16px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    color: #606266;
    font-weight: 500;
    transition: all 0.3s;
}

.tab-btn.active {
    color: #409eff;
    border-bottom-color: #409eff;
    background: rgba(64, 158, 255, 0.05);
    border-radius: 4px 4px 0 0;
}

.tab-btn:hover:not(.active) {
    color: #303133;
    background: rgba(0,0,0,0.02);
}


/* Layouts */
.student-wrapper-layout {
    display: grid;
    gap: 24px;
    grid-template-columns: 1fr 350px; /* List takes left, Upload takes right */
    grid-template-areas: 
        "list upload";
    align-items: start;
}

@media (max-width: 1000px) {
    .student-wrapper-layout {
        grid-template-columns: 1fr;
        grid-template-areas: 
            "upload"
            "list";
    }
}

.archive-wrapper-layout {
    /* Stack vertically */
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.list-section {
    grid-area: list;
}
.upload-section {
    grid-area: upload;
}


/* Cards */
.card {
    background: #fff;
    border-radius: 8px;
    padding: 24px;
    box-shadow: 0 1px 2px -2px rgba(0,0,0,0.16), 0 3px 6px 0 rgba(0,0,0,0.12), 0 5px 12px 4px rgba(0,0,0,0.09);
    height: fit-content;
}

h3 {
    margin: 0 0 8px 0;
    color: #303133;
    font-size: 18px;
}

.subtitle {
    font-size: 13px;
    color: #909399;
    margin-bottom: 20px;
}

/* Upload Section */
.upload-area {
    display: flex;
    flex-direction: column;
    gap: 15px;
}

.file-input-label {
    border: 2px dashed #d9d9d9;
    background: #fafafa;
    border-radius: 6px;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: border-color 0.3s;
    color: #606266;
    gap: 8px;
}
.file-input-label:hover {
    border-color: #409eff;
    color: #409eff;
}

/* Buttons */
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
.primary-btn:disabled {
    background: #a0cfff;
    cursor: not-allowed;
}

.warning-btn {
    background: #E6A23C;
    color: white;
    border: none;
    padding: 10px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
}
.warning-btn:hover { background: #ebb563; }
.warning-btn:disabled { background: #f3d19e; cursor: not-allowed; }

.danger-btn {
    background: #fef0f0;
    color: #f56c6c;
    border: 1px solid #fbc4c4;
    padding: 8px 16px;
    border-radius: 4px;
    cursor: pointer;
}

.secondary-btn {
    background: #fff;
    border: 1px solid #dcdfe6;
    color: #606266;
    padding: 8px 16px;
    border-radius: 4px;
    cursor: pointer;
}
.secondary-btn.active {
    color: #409eff;
    border-color: #c6e2ff;
    background-color: #ecf5ff;
}
.secondary-btn.small, .primary-btn.small {
    padding: 5px 12px;
    font-size: 12px;
}

.refresh-btn {
    background: transparent;
    border: none;
    color: #409eff;
    cursor: pointer;
}
.refresh-btn:hover { text-decoration: underline; }

.action-btn {
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid #dcdfe6;
    background: #fff;
    cursor: pointer;
    font-size: 12px;
    margin-right: 5px;
}
.action-btn:hover { color: #409eff; border-color: #c6e2ff; }
.action-btn.danger { color: #f56c6c; border-color: #fbc4c4; background: #fef0f0; }
.action-btn.success { color: #67c23a; border-color: #e1f3d8; background: #f0f9eb; }

/* Table */
.table-container {
    overflow-x: auto;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
}
th, td {
    padding: 12px 8px;
    text-align: left;
    border-bottom: 1px solid #ebeef5;
}
th {
    background-color: #f5f7fa;
    color: #909399;
    font-weight: 600;
}
.badge {
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 12px;
    color: #fff;
}
.badge.green { background: #6ebd47; }
.badge.red { background: #f56c6c; }
.badge.blue { background: #409eff; }
.badge.yellow { background: #E6A23C; }
.badge.gray { background: #909399; }
.badge.clickable { cursor: pointer; user-select: none; }

.status-text { font-size: 12px; color: #909399; }
.status-text.set { color: #67c23a; }

.empty-text {
    text-align: center;
    padding: 20px;
    color: #909399;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
}

/* Modals */
.modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 999;
}
.modal-box {
    background: #fff;
    border-radius: 8px;
    width: 90%;
    max-width: 800px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
}
.modal-header {
    padding: 15px 20px;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #909399; }
.modal-content {
    padding: 20px;
    overflow-y: auto;
}
.form-group { margin-bottom: 15px; }
.form-group label { display: block; margin-bottom: 5px; color: #606266; }
.text-input {
    width: 100%;
    padding: 8px;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
}
.form-group.row {
    display: flex;
    align-items: center;
    gap: 10px;
}
.form-group.row label { margin-bottom: 0; }
.hint { font-size: 12px; color: #909399; }
.error-msg { color: #f56c6c; margin-top: 10px; font-size: 12px; }
.modal-footer { margin-top: 20px; text-align: right; }

/* Progress Table in Modal */
.prob-header {
    background: #f5f7fa;
    padding: 8px 12px;
    border-radius: 4px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
}
.prob-info { display: flex; align-items: center; gap: 10px; }
.prob-pdf-status { font-size: 13px; font-weight: normal; }
.pdf-download-link { color: #409eff; text-decoration: none; }
.pdf-download-link:hover { text-decoration: underline; }
.pdf-not-uploaded { color: #909399; }
.progress-list { display: flex; flex-direction: column; gap: 15px; }
.input-table { width: 100%; border: 1px solid #ebeef5; }
.input-table th { background: #fff; }
.tiny-input { width: 40px; padding: 2px 4px; border: 1px solid #dcdfe6; border-radius: 2px; text-align: center; }
.attempt-edit { display: flex; align-items: center; gap: 4px; }
.save-btn { font-size: 11px; padding: 2px 6px; background: #ecf5ff; border: 1px solid #d9ecff; color: #409eff; cursor: pointer; }
.reset-btn { font-size: 11px; padding: 2px 6px; background: #fff; border: 1px solid #dcdfe6; margin-left: 5px; cursor: pointer; }
</style>
