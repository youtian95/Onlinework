<template>
    <div class="card mb-4">
            <div class="upload-container">
            <h3>📤 上传新题目</h3>
            
            <div class="form-row">
                <div class="form-group">
                    <label>题目ID (英文ID，如 demo-03)</label>
                    <input type="text" v-model="problemId" placeholder="例如: new-problem-01" class="text-input" />
                </div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label>选择文件 (多选，需包含 .py 和 .md)</label>
                    <div class="file-box">
                            <input type="file" ref="fileInput" multiple @change="handleFileChange" hidden />
                            <button class="outline-btn" @click="$refs.fileInput.click()">
                            {{ files.length > 0 ? `已选 ${files.length} 个文件` : '点击选择文件' }}
                            </button>
                    </div>
                </div>
            </div>

            <div class="form-row" v-if="files.length > 0">
                    <div class="form-group">
                    <label>选择主验算脚本 (将被重命名为 script.py)</label>
                        <select v-model="mainScript" class="select-input">
                        <option v-for="f in pyFiles" :key="f.name" :value="f.name">{{ f.name }}</option>
                        </select>
                </div>
                <div class="form-group">
                    <label>选择题目描述 (将被重命名为 problem.md)</label>
                        <select v-model="mainMd" class="select-input">
                        <option v-for="f in mdFiles" :key="f.name" :value="f.name">{{ f.name }}</option>
                        </select>
                </div>
            </div>

            <div class="upload-actions">
                    <button 
                    @click="uploadProblem" 
                    class="primary-btn" 
                    :disabled="uploading || !canUpload"
                    >
                    {{ uploading ? '上传中...' : '确认上传' }}
                    </button>
                    <span v-if="successMessage" class="success-msg">{{ successMessage }}</span>
            </div>
            </div>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'

const props = defineProps({
    adminToken: String
})

const emit = defineEmits(['logout', 'uploaded'])

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

// Upload State
const problemId = ref('')
const files = ref([])
const mainScript = ref('')
const mainMd = ref('')
const uploading = ref(false)
const fileInput = ref(null)
const successMessage = ref('')

const pyFiles = computed(() => files.value.filter(f => f.name.endsWith('.py')))
const mdFiles = computed(() => files.value.filter(f => f.name.endsWith('.md')))
const canUpload = computed(() => problemId.value && mainScript.value && mainMd.value)

const handleFileChange = (e) => {
    files.value = Array.from(e.target.files)
    // Auto preset if possible
    if (pyFiles.value.length === 1) mainScript.value = pyFiles.value[0].name
    if (mdFiles.value.length === 1) mainMd.value = mdFiles.value[0].name
    successMessage.value = ''
}

const uploadProblem = async () => {
    if (!canUpload.value) return
    uploading.value = true
    successMessage.value = ''
    
    const formData = new FormData()
    formData.append('problem_id', problemId.value)
    formData.append('main_script', mainScript.value)
    formData.append('main_md', mainMd.value)
    
    files.value.forEach(f => {
        formData.append('files', f)
    })
    
    try {
        await axios.post(`${API_BASE_URL}/admin/problems/upload`, formData, {
            headers: { 
                'X-Admin-Token': props.adminToken,
                'Content-Type': 'multipart/form-data'
            }
        })
        successMessage.value = `题目 ${problemId.value} 上传成功!`
        
        // Reset form
        const createdProblemId = problemId.value
        problemId.value = ''
        files.value = []
        mainScript.value = ''
        mainMd.value = ''
        if (fileInput.value) fileInput.value.value = ''
        
        emit('uploaded', createdProblemId)
        
        setTimeout(() => successMessage.value = '', 3000)
    } catch (e) {
        console.error(e)
        if (e.response?.status === 401) emit('logout')
        else alert('上传失败: ' + (e.response?.data?.detail || '未知错误'))
    } finally {
        uploading.value = false
    }
}
</script>

<style scoped>
.mb-4 { margin-bottom: 24px; }

.upload-container {
    display: flex;
    flex-direction: column;
    gap: 15px;
}
.upload-container h3 {
    margin: 0; 
    font-size: 18px; 
    color: #303133;
    padding-bottom: 10px;
    border-bottom: 1px solid #f0f2f5;
}

.form-row {
    display: flex;
    gap: 20px;
    align-items: flex-end;
}
.form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1;
}
.form-group label {
    font-size: 13px;
    color: #909399;
    font-weight: 500;
}
.text-input, .select-input {
    padding: 8px 10px;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
}
.text-input:focus, .select-input:focus {
    border-color: #409eff;
}
.file-box {
    display: flex;
    align-items: center;
}

.outline-btn { border: 1px solid #dcdfe6; background: white; padding: 8px 16px; border-radius: 4px; cursor: pointer; color: #606266; font-size: 14px; }
.outline-btn:hover { color: #409eff; border-color: #c6e2ff; }
.primary-btn { background: #409eff; color: white; border: none; padding: 8px 24px; border-radius: 4px; cursor: pointer; font-size: 14px; height: 36px; }
.primary-btn:disabled { background: #a0cfff; cursor: not-allowed; }

.upload-actions {
    display: flex;
    align-items: center;
    gap: 15px;
    margin-top: 10px;
}
.success-msg {
    color: #67c23a;
    font-size: 14px;
    font-weight: 500;
}

.card {
    background: #fff;
    border-radius: 8px;
    padding: 24px;
    box-shadow: 0 1px 2px -2px rgba(0,0,0,0.16), 0 3px 6px 0 rgba(0,0,0,0.12), 0 5px 12px 4px rgba(0,0,0,0.09);
    height: fit-content;
}
</style>
