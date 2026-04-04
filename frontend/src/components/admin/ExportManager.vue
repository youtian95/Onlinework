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
                    <span class="desc">导出所有学生的各题目得分明细表格 (XLSX)</span>
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
import JSZip from 'jszip'
import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'
import { marked } from 'marked'
import markedKatex from 'marked-katex-extension'
// 引入样式，保证前端能正确渲染 Markdown 和 KaTex 以便 html2pdf 截图
import 'github-markdown-css/github-markdown.css'

// 注册 Katex 插件
marked.use(markedKatex({ throwOnError: false, trust: true, strict: 'ignore' }))

const props = defineProps({
    adminToken: String
})

const loadingScores = ref(false)
const loadingWork = ref(false)
const loadingDB = ref(false)
const loadingImport = ref(false)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

const waitForNextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve()))

const prepareImages = async (container) => {
    const images = Array.from(container.querySelectorAll('img'))

    await Promise.all(images.map((img) => {
        const src = img.getAttribute('src') || ''
        if (!src || (!src.startsWith('http') && !src.startsWith('data:') && !src.startsWith('blob:'))) {
            img.remove()
            return Promise.resolve()
        }

        img.crossOrigin = 'anonymous'

        if (img.complete) {
            return Promise.resolve()
        }

        return new Promise((resolve) => {
            img.onload = () => resolve()
            img.onerror = () => {
                img.remove()
                resolve()
            }
        })
    }))
}

const renderMarkdownToPdfBlob = async (mdContent) => {
    const container = document.createElement('div')
    container.className = 'markdown-body export-pdf-render-root'
    container.style.position = 'fixed'
    container.style.left = '0'
    container.style.top = '0'
    container.style.width = '794px'
    container.style.padding = '24px'
    container.style.background = '#ffffff'
    container.style.color = '#000000'
    container.style.zIndex = '99999'
    container.style.pointerEvents = 'none'
    container.style.boxSizing = 'border-box'
    container.style.overflow = 'visible'
    container.innerHTML = marked.parse(mdContent)

    document.body.appendChild(container)

    try {
        await waitForNextFrame()
        await waitForNextFrame()
        await prepareImages(container)
        await waitForNextFrame()

        const canvas = await html2canvas(container, {
            backgroundColor: '#ffffff',
            scale: 2,
            useCORS: true,
            logging: false,
            imageTimeout: 0,
            scrollX: 0,
            scrollY: 0,
            windowWidth: Math.ceil(container.scrollWidth),
            windowHeight: Math.ceil(container.scrollHeight)
        })

        const pdf = new jsPDF({
            orientation: 'portrait',
            unit: 'mm',
            format: 'a4'
        })

        const margin = 10
        const pageWidth = pdf.internal.pageSize.getWidth()
        const pageHeight = pdf.internal.pageSize.getHeight()
        const renderWidth = pageWidth - margin * 2
        const pageContentHeight = pageHeight - margin * 2
        const pageCanvasHeight = Math.floor((pageContentHeight * canvas.width) / renderWidth)

        let offsetY = 0
        let isFirstPage = true

        while (offsetY < canvas.height) {
            const sliceHeight = Math.min(pageCanvasHeight, canvas.height - offsetY)
            const pageCanvas = document.createElement('canvas')
            pageCanvas.width = canvas.width
            pageCanvas.height = sliceHeight

            const pageContext = pageCanvas.getContext('2d')
            pageContext.drawImage(
                canvas,
                0,
                offsetY,
                canvas.width,
                sliceHeight,
                0,
                0,
                canvas.width,
                sliceHeight
            )

            const pageImage = pageCanvas.toDataURL('image/png')
            const pageRenderHeight = (sliceHeight * renderWidth) / canvas.width

            if (!isFirstPage) {
                pdf.addPage()
            }

            pdf.addImage(pageImage, 'PNG', margin, margin, renderWidth, pageRenderHeight, undefined, 'FAST')
            offsetY += sliceHeight
            isFirstPage = false
        }

        return pdf.output('blob')
    } finally {
        document.body.removeChild(container)
    }
}

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
        link.setAttribute('download', `scores_${new Date().toISOString().slice(0,10)}.xlsx`)
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
            responseType: 'arraybuffer'
        })
        
        // 1. 使用 JSZip 读取后端返回的 ZIP 文件
        const zip = await JSZip.loadAsync(response.data)
        const mdFiles = []
        
        zip.forEach((relativePath, zipEntry) => {
            if (relativePath.endsWith('.md')) {
                mdFiles.push(zipEntry)
            }
        })
        
        if (mdFiles.length > 0) {
            for (let i = 0; i < mdFiles.length; i++) {
                const entry = mdFiles[i]
                const mdContent = await entry.async("string")
                const pdfBlob = await renderMarkdownToPdfBlob(mdContent)
                
                // 将新拿到的 Blob PDF 塞进现在的压缩包里相同的学生目录下
                const pdfPath = entry.name.replace('.md', '.pdf')
                zip.file(pdfPath, pdfBlob)
            }
        }
        
        // 4. 全部渲染完成后重新打包带 pdf 的 zip 并触发下载
        const finalZipBlob = await zip.generateAsync({ type: 'blob' })
        const url = window.URL.createObjectURL(finalZipBlob)
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `student_work_${new Date().toISOString().slice(0,10)}.zip`)
        document.body.appendChild(link)
        link.click()
        link.remove()
        
    } catch (e) {
        alert('下载失败: 解析或生成 PDF 时出错，请查看控制台排查原因。')
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