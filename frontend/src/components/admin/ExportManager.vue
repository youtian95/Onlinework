<template>
  <div class="export-manager">
    <div class="card">
        <div class="card-header">
            <h3>数据导出</h3>
        </div>
        <div class="card-body">
            <div class="export-section">
                <div class="section-header">
                    <h4>📊 成绩报表</h4>
                    <span class="desc">导出所有学生的各题目得分明细表格 (CSV)</span>
                </div>
                <div class="section-action">
                    <button @click="downloadScores" class="primary-btn" :disabled="loadingScores">
                        {{ loadingScores ? '正在生成...' : '下载成绩表' }}
                    </button>
                </div>
            </div>
            
            <div class="export-section">
                <div class="section-header">
                    <h4>📂 学生作业归档</h4>
                    <span class="desc">导出包含所有学生作业的 Markdown 及 PDF 文件的压缩包 (ZIP)</span>
                    <p class="warning">⚠️ 此操作涉及大量文件生成，可能需要较长时间，请耐心等待。</p>
                </div>
                <div class="section-action">
                    <button @click="downloadWork" class="primary-btn warning" :disabled="loadingWork">
                        {{ loadingWork ? '正在打包...' : '下载作业归档' }}
                    </button>
                </div>
            </div>

            <div class="export-section">
                <div class="section-header">
                    <h4>💾 数据库备份与恢复</h4>
                    <span class="desc">导出/导入完整数据库 (CSV)。用于迁移数据或学期存档。</span>
                </div>
                <div class="section-action group">
                    <button @click="downloadDB" class="primary-btn info" :disabled="loadingDB">
                        {{ loadingDB ? '正在导出...' : '导出全库' }}
                    </button>
                    
                    <button @click="$refs.dbImportInput.click()" class="primary-btn" :disabled="loadingImport">
                        {{ loadingImport ? '正在导入...' : '导入恢复' }}
                    </button>
                    <input type="file" ref="dbImportInput" class="hidden-input" accept=".zip" @change="importDB" />
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const props = defineProps({
    adminToken: String
})

const loadingScores = ref(false)
const loadingWork = ref(false)
const loadingDB = ref(false)
const loadingImport = ref(false)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

const downloadScores = async () => {
    loadingScores.value = true
    try {
        const response = await axios.get(`${API_BASE_URL}/admin/export/scores`, {
            params: { token: props.adminToken },
            responseType: 'blob' 
        })
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `scores_${new Date().toISOString().slice(0,10)}.csv`)
        document.body.appendChild(link)
        link.click()
        link.remove()
    } catch (e) {
        alert('下载失败')
        console.error(e)
    } finally {
        loadingScores.value = false
    }
}

const downloadWork = async () => {
    loadingWork.value = true
    try {
        const response = await axios.get(`${API_BASE_URL}/admin/export/work`, {
            params: { token: props.adminToken },
            responseType: 'blob'
        })
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `student_work_${new Date().toISOString().slice(0,10)}.zip`)
        document.body.appendChild(link)
        link.click()
        link.remove()
    } catch (e) {
        alert('下载失败')
        console.error(e)
    } finally {
        loadingWork.value = false
    }
}

const downloadDB = async () => {
    loadingDB.value = true
    try {
        const response = await axios.get(`${API_BASE_URL}/admin/export/db_dump`, {
            params: { token: props.adminToken },
            responseType: 'blob'
        })
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `db_dump_${new Date().toISOString().slice(0,10)}.zip`)
        document.body.appendChild(link)
        link.click()
        link.remove()
    } catch (e) {
        alert('导出失败')
        console.error(e)
    } finally {
        loadingDB.value = false
    }
}

const importDB = async (event) => {
    const file = event.target.files[0]
    if (!file) return
    
    if (!confirm('警告：此操作将清空当前所有数据并从备份文件恢复！确定要继续吗？')) {
        event.target.value = ''
        return
    }
    
    loadingImport.value = true
    const formData = new FormData()
    formData.append('file', file)
    
    try {
        await axios.post(`${API_BASE_URL}/admin/export/db_restore`, formData, {
            params: { token: props.adminToken },
            headers: { 'Content-Type': 'multipart/form-data' }
        })
        alert('恢复成功！')
        // Maybe reload page
        window.location.reload()
    } catch (e) {
        alert('恢复失败: ' + (e.response?.data?.detail || e.message))
    } finally {
        loadingImport.value = false
        event.target.value = ''
    }
}
</script>

<style scoped>
.export-manager {
    max-width: 1200px;
    margin: 0 auto;
}
.card {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
    overflow: hidden;
}
.card-header {
    padding: 15px 20px;
    border-bottom: 1px solid #ebeef5;
    background-color: #f5f7fa;
}
.card-header h3 { margin: 0; color: #303133; }
.card-body { padding: 20px; }

.export-section {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    margin-bottom: 20px;
    background: #fff;
    transition: 0.3s;
}
.export-section:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.section-header h4 { margin: 0 0 5px 0; color: #303133; font-size: 16px; }
.desc { color: #606266; font-size: 14px; }
.warning { color: #e6a23c; font-size: 12px; margin: 8px 0 0 0; }

.section-action.group {
    display: flex;
    gap: 10px;
}

.primary-btn {
    background: #409eff;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    transition: 0.3s;
}
.primary-btn:hover { background: #66b1ff; }
.primary-btn:disabled { background: #a0cfff; cursor: not-allowed; }

.primary-btn.warning {
    background: #e6a23c;
}
.primary-btn.warning:hover {
    background: #ebb563;
}
.primary-btn.info {
    background: #909399;
}
.primary-btn.info:hover {
    background: #a6a9ad;
}

.hidden-input {
    display: none;
}
.primary-btn.warning:disabled {
    background: #f3d19e;
}

@media (max-width: 768px) {
    .export-section {
        flex-direction: column;
        align-items: flex-start;
        gap: 15px;
    }
    .section-action {
        width: 100%;
        text-align: right;
    }
}
</style>