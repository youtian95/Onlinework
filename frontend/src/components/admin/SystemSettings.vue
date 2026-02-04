<template>
  <div class="settings-wrapper">
    <div class="card">
        <h3>🎨 系统外观设置</h3>
        <p class="subtitle">设置登录页的标题和背景图片</p>
        
        <div class="setting-form">
            <div class="form-group">
                <label>课程/系统名称</label>
                <div class="input-row">
                    <textarea v-model="courseName" class="text-input" placeholder="默认为: 在线作业系统" rows="3"></textarea>
                    <button @click="saveName" class="primary-btn" :disabled="saving">
                        {{ saving ? '保存中...' : '保存名称' }}
                    </button>
                </div>
            </div>
            
            <div class="form-group">
                <label>登录页封面图片</label>
                <div class="upload-row">
                    <div class="preview-box">
                        <img v-if="coverUrl" :src="fullCoverUrl" class="preview-img" alt="Current Cover"/>
                        <div v-else class="placeholder">无自定义封面</div>
                    </div>
                    
                    <div class="upload-action">
                        <label class="file-btn">
                            📁 选择图片
                            <input type="file" accept="image/*" @change="handleFileChange" hidden />
                        </label>
                        <span v-if="file" class="filename">{{ file.name }}</span>
                        <button v-if="file" @click="uploadCover" class="primary-btn" :disabled="uploading">
                            {{ uploading ? '上传中...' : '确认上传' }}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'

const props = defineProps({
    adminToken: String
})

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

const courseName = ref('')
const coverUrl = ref('')
const file = ref(null)
const saving = ref(false)
const uploading = ref(false)

const fullCoverUrl = computed(() => {
    if (!coverUrl.value) return ''
    if (coverUrl.value.startsWith('http')) return coverUrl.value
    return `${API_BASE_URL}${coverUrl.value}`
})

const fetchSettings = async () => {
    try {
        const res = await axios.get(`${API_BASE_URL}/system/settings`)
        courseName.value = res.data.course_name
        coverUrl.value = res.data.cover_image
    } catch (e) {
        console.error("Failed to fetch settings", e)
    }
}

const saveName = async () => {
    saving.value = true
    try {
        await axios.put(`${API_BASE_URL}/system/admin/settings`, 
            { course_name: courseName.value }, 
            { headers: { Authorization: `Bearer ${props.adminToken}` } } // Headers handled by interceptor ideally, but doing manually for now
        )
        alert("系统名称已更新")
    } catch (e) {
        alert("保存失败")
    } finally {
        saving.value = false
    }
}

const handleFileChange = (e) => {
    const files = e.target.files
    if (files.length > 0) {
        file.value = files[0]
    }
}

const uploadCover = async () => {
    if (!file.value) return
    uploading.value = true
    
    const formData = new FormData()
    formData.append('file', file.value)
    
    try {
        const res = await axios.post(`${API_BASE_URL}/system/admin/cover`, formData, {
            headers: { 
                'Content-Type': 'multipart/form-data',
                Authorization: `Bearer ${props.adminToken}`
            }
        })
        coverUrl.value = res.data.url
        file.value = null
        alert("封面已更新")
    } catch (e) {
        alert("上传失败: " + (e.response?.data?.detail || e.message))
    } finally {
        uploading.value = false
    }
}

onMounted(() => {
    fetchSettings()
})
</script>

<style scoped>
.settings-wrapper {
    max-width: 800px;
    margin: 0 auto;
}
.card {
    background: #fff;
    padding: 30px;
    border-radius: 8px;
    box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
}
h3 { margin-top: 0; margin-bottom: 5px; }
.subtitle { color: #909399; font-size: 14px; margin-bottom: 25px; }

.form-group { margin-bottom: 30px; }
.form-group label { display: block; margin-bottom: 10px; font-weight: 500; color: #303133; }

.input-row { display: flex; gap: 10px; max-width: 500px; }
.text-input { flex: 1; padding: 10px; border: 1px solid #dcdfe6; border-radius: 4px; }

.upload-row { display: flex; align-items: flex-start; gap: 20px; }
.preview-box {
    width: 200px;
    height: 120px;
    border: 1px dashed #dcdfe6;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: #f5f7fa;
}
.preview-img { width: 100%; height: 100%; object-fit: cover; }
.placeholder { color: #909399; font-size: 12px; }

.upload-action { display: flex; flex-direction: column; gap: 10px; }
.file-btn {
    display: inline-block;
    padding: 8px 16px;
    background: #ecf5ff;
    border: 1px solid #b3d8ff;
    color: #409eff;
    border-radius: 4px;
    cursor: pointer;
    text-align: center;
    font-size: 14px;
}
.file-btn:hover { background: #409eff; color: white; border-color: #409eff; }

.primary-btn {
    padding: 10px 20px;
    background: #409eff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}
.primary-btn:disabled { background: #a0cfff; cursor: not-allowed; }
.filename { font-size: 12px; color: #606266; }
</style>