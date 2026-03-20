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

            <div v-if="showTeamworkModal" class="modal-overlay" @click.self="closeTeamworkModal">
                <div class="modal-box">
                    <div class="modal-header">
                        <h3>配置团队作业</h3>
                        <button type="button" class="close-btn" @click="closeTeamworkModal">×</button>
                    </div>

                    <div class="modal-body">
                        <p class="modal-tip">检测到该题目为团队作业，请设置队伍数量和每队人数。</p>

                        <div class="form-group">
                            <label>队伍数量</label>
                            <input v-model="teamworkTeamCount" type="number" min="1" class="text-input" />
                        </div>

                        <div class="form-group">
                            <label>每队人数</label>
                            <input v-model="teamworkTeamSize" type="number" min="1" class="text-input" :disabled="teamworkTeamSizeLocked" />
                            <div v-if="teamworkTeamSizeLocked" class="help-text">已有团队配置时，人数不可修改。</div>
                        </div>
                    </div>

                    <div class="modal-footer">
                        <button type="button" class="outline-btn" @click="closeTeamworkModal">取消</button>
                        <button type="button" class="primary-btn" @click="confirmTeamworkUpload">继续上传</button>
                    </div>
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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// Upload State
const problemId = ref('')
const files = ref([])
const mainScript = ref('')
const mainMd = ref('')
const uploading = ref(false)
const fileInput = ref(null)
const successMessage = ref('')
const showTeamworkModal = ref(false)
const teamworkTeamCount = ref('')
const teamworkTeamSize = ref('')
const teamworkTeamSizeLocked = ref(false)
const pendingUploadContext = ref(null)

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

const checkProblemExists = async (targetProblemId) => {
    const res = await axios.get(`${API_BASE_URL}/admin/problems`, {
        headers: { 'X-Admin-Token': props.adminToken }
    })
    return Array.isArray(res.data) && res.data.some(p => p.id === targetProblemId)
}

const getSelectedMainScriptFile = () => {
    return files.value.find(f => f.name === mainScript.value) || null
}

const readSelectedMainScript = async () => {
    const file = getSelectedMainScriptFile()
    if (!file) return ''
    return await file.text()
}

const parseTeamworkDefaultsFromScript = (content) => {
    const teamCountMatch = content.match(/["']team_count["']\s*:\s*(\d+)/)
    const teamSizeMatch = content.match(/["']team_size["']\s*:\s*(\d+)/)
    return {
        teamCount: teamCountMatch ? teamCountMatch[1] : '',
        teamSize: teamSizeMatch ? teamSizeMatch[1] : '',
    }
}

const detectTeamworkProblem = async () => {
    const content = await readSelectedMainScript()
    return {
        isTeamwork: /["']teamwork["']\s*:/.test(content),
        defaults: parseTeamworkDefaultsFromScript(content),
    }
}

const fetchExistingTeamworkConfig = async (targetProblemId) => {
    try {
        const res = await axios.get(`${API_BASE_URL}/admin/teamwork/${encodeURIComponent(targetProblemId)}/config`, {
            headers: { 'X-Admin-Token': props.adminToken }
        })
        return res.data
    } catch {
        return null
    }
}

const closeTeamworkModal = () => {
    showTeamworkModal.value = false
    pendingUploadContext.value = null
}

const performUpload = async (context) => {
    uploading.value = true
    successMessage.value = ''

    const formData = new FormData()
    formData.append('problem_id', context.normalizedProblemId)
    formData.append('main_script', mainScript.value)
    formData.append('main_md', mainMd.value)

    files.value.forEach(f => {
        formData.append('files', f)
    })

    if (context.teamwork) {
        formData.append('team_count', String(context.teamCount))
        formData.append('team_size', String(context.teamSize))
    }

    try {
        await axios.post(`${API_BASE_URL}/admin/problems/upload`, formData, {
            headers: {
                'X-Admin-Token': props.adminToken,
                'Content-Type': 'multipart/form-data'
            }
        })
        successMessage.value = context.isDuplicateProblemId
            ? `题目 ${context.normalizedProblemId} 已覆盖更新!`
            : `题目 ${context.normalizedProblemId} 上传成功!`

        const createdProblemId = context.normalizedProblemId
        problemId.value = ''
        files.value = []
        mainScript.value = ''
        mainMd.value = ''
        teamworkTeamCount.value = ''
        teamworkTeamSize.value = ''
        teamworkTeamSizeLocked.value = false
        pendingUploadContext.value = null
        showTeamworkModal.value = false
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

const confirmTeamworkUpload = async () => {
    const teamCount = Number(teamworkTeamCount.value)
    const teamSize = Number(teamworkTeamSize.value)

    if (!Number.isInteger(teamCount) || teamCount <= 0) {
        alert('请输入有效的队伍数量')
        return
    }
    if (!Number.isInteger(teamSize) || teamSize <= 0) {
        alert('请输入有效的每队人数')
        return
    }
    if (!pendingUploadContext.value) {
        closeTeamworkModal()
        return
    }

    await performUpload({
        ...pendingUploadContext.value,
        teamwork: true,
        teamCount,
        teamSize,
    })
}

const uploadProblem = async () => {
    if (!canUpload.value) return
    const normalizedProblemId = problemId.value.trim()
    if (!normalizedProblemId) return
    successMessage.value = ''
    
    try {
        const isDuplicateProblemId = await checkProblemExists(normalizedProblemId)
        if (isDuplicateProblemId) {
            const shouldOverwrite = window.confirm(
                `题目ID「${normalizedProblemId}」已存在，继续上传将覆盖更新该题目。是否继续？`
            )
            if (!shouldOverwrite) {
                return
            }
        }

        const teamworkInfo = await detectTeamworkProblem()
        if (teamworkInfo.isTeamwork) {
            const existingConfig = isDuplicateProblemId
                ? await fetchExistingTeamworkConfig(normalizedProblemId)
                : null

            teamworkTeamCount.value = String(existingConfig?.config?.team_count ?? teamworkInfo.defaults.teamCount ?? '')
            teamworkTeamSize.value = String(existingConfig?.config?.team_size ?? teamworkInfo.defaults.teamSize ?? '')
            teamworkTeamSizeLocked.value = !!existingConfig?.configured
            pendingUploadContext.value = {
                normalizedProblemId,
                isDuplicateProblemId,
            }
            showTeamworkModal.value = true
            return
        }

        await performUpload({
            normalizedProblemId,
            isDuplicateProblemId,
            teamwork: false,
        })
    } catch (e) {
        console.error(e)
        if (e.response?.status === 401) emit('logout')
        else alert('上传失败: ' + (e.response?.data?.detail || '未知错误'))
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

.modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 300;
}

.modal-box {
    width: 420px;
    max-width: calc(100vw - 24px);
    background: #fff;
    border-radius: 10px;
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.18);
}

.modal-header,
.modal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 18px;
}

.modal-header {
    border-bottom: 1px solid #eef2f7;
}

.modal-header h3 {
    margin: 0;
    font-size: 18px;
    color: #1f2937;
}

.modal-body {
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.modal-tip {
    margin: 0;
    color: #4b5563;
    font-size: 14px;
}

.modal-footer {
    justify-content: flex-end;
    gap: 12px;
    border-top: 1px solid #eef2f7;
}

.close-btn {
    border: none;
    background: none;
    font-size: 24px;
    cursor: pointer;
    color: #94a3b8;
}

.help-text {
    font-size: 12px;
    color: #6b7280;
}
</style>
