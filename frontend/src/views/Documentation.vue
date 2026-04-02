<template>
  <div class="docs-layout">
    <!-- 侧边目录 -->
    <aside class="docs-sidebar">
      <div class="toc-header">目录</div>
      <ul class="toc-list">
        <li 
          v-for="(item, index) in toc" 
          :key="index"
          :class="['toc-item', `toc-level-${item.level}`, { 'active': activeSlug === item.slug }]"
          @click="scrollTo(item.slug)"
        >
          {{ item.text }}
        </li>
      </ul>
    </aside>

    <!-- 文档内容 -->
    <div class="docs-main">
      <div class="docs-card">
        <div class="doc-actions">
           <button @click="router.back()" class="home-btn">← 返回上一页</button>
        </div>
        <div class="markdown-body" v-html="renderedContent"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import rawDocContent from '../../../docs/guide.md?raw'
import 'github-markdown-css/github-markdown-light.css'

const router = useRouter()
const toc = ref([])
const activeSlug = ref('')

// ... renderer ...

// 自定义 Renderer 以提取标题生成目录
const renderer = new marked.Renderer()
// 临时存储目录，避免 computed 副作用
let tempToc = []
let headingCount = 0

renderer.heading = (text, level) => {
    const slug = 'heading-' + (headingCount++)
    
    // 优化：目录只显示 H2-H4，忽略 H1 (文档大标题) 以及过深的层级
    if (level >= 2 && level <= 4) {
        tempToc.push({ text, level, slug })
    }
    
    // 返回带 ID 的 HTML
    return `<h${level} id="${slug}">${text}</h${level}>`
}

const renderedContent = computed(() => {
    tempToc = [] // 重置目录
    headingCount = 0 // 重置计数器
    const html = marked(rawDocContent, { renderer })
    toc.value = [...tempToc] // 更新响应式目录
    return html
})

const scrollTo = (id) => {
    const el = document.getElementById(id)
    if (el) {
        // 减去一些头部偏移量，避免贴着顶端
        const offset = 80
        const bodyRect = document.body.getBoundingClientRect().top
        const elementRect = el.getBoundingClientRect().top
        const elementPosition = elementRect - bodyRect
        const offsetPosition = elementPosition - offset

        window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
        })
        activeSlug.value = id
    }
}

const updateActiveHeading = () => {
    const headings = Array.from(document.querySelectorAll('.markdown-body h2, .markdown-body h3, .markdown-body h4'))
    if (headings.length === 0) return

    // 获取滚动距离
    const scrollY = window.scrollY
    // 偏移阈值，判定线在屏幕上方一部分
    const offset = 120 

    // 找到第一个"位置 > 当前滚动位置 + 偏移"的标题，它的前一个就是当前由于阅读的标题
    let currentId = headings[0].id
    
    for (let i = 0; i < headings.length; i++) {
        // offsetTop 是相对于父级定位元素的，如果这里父级不是body可能要注意
        // 这里的 markdown-body 默认是静态定位，所以 offsetTop 应该是准的（相对于页面顶部）
        if (headings[i].offsetTop > scrollY + offset) {
            if (i > 0) {
                currentId = headings[i-1].id
            }
            break
        }
        // 如果遍历完了，说明所有标题都在上面，取最后一个
        if (i === headings.length - 1) {
            currentId = headings[i].id
        }
    }
    
    activeSlug.value = currentId
}

onMounted(() => {
    window.addEventListener('scroll', updateActiveHeading)
    nextTick(() => {
        updateActiveHeading()
    })
})

onUnmounted(() => {
    window.removeEventListener('scroll', updateActiveHeading)
})
</script>

<style scoped>
.docs-layout {
  display: flex;
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  gap: 20px;
}

/* Sidebar */
.docs-sidebar {
  width: 250px;
  flex-shrink: 0;
  position: sticky;
  top: 20px;
  height: calc(100vh - 40px);
  overflow-y: auto;
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}

.toc-header {
  font-weight: bold;
  font-size: 16px;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #eee;
}

.toc-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.toc-item {
  font-size: 14px;
  color: #606266;
  padding: 4px 0;
  cursor: pointer;
  transition: color 0.2s;
  line-height: 1.5;
}

.toc-item:hover {
  color: #409eff;
}

.toc-item.active {
  color: #409eff;
  background-color: #ecf5ff;
  border-right: 3px solid #409eff;
}

/* 目录分级样式 */
/* H2 作为一级目录显示 */
.toc-level-2 { font-weight: 600; color: #303133; margin-top: 10px; }
/* H3 作为二级目录 - 缩进 */
.toc-level-3 { padding-left: 15px; color: #606266; }
/* H4 作为三级目录 - 更深缩进 + 小字体 */
.toc-level-4 { padding-left: 30px; font-size: 13px; color: #909399; }

/* Main Content */
.docs-main {
  flex: 1;
  min-width: 0; /* 防止 flex 子项溢出 */
}

.docs-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
  padding: 40px;
  min-height: 80vh;
}

.doc-actions {
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eaecef;
}

.home-btn {
  background: transparent;
  border: 1px solid #dcdfe6;
  color: #606266;
  cursor: pointer;
  padding: 8px 16px;
  border-radius: 4px;
  font-size: 14px;
  transition: all 0.3s;
  display: inline-flex;
  align-items: center;
}

.home-btn:hover {
  color: #409eff;
  border-color: #c6e2ff;
  background-color: #ecf5ff;
}

.doc-nav {
  margin-bottom: 20px;
  padding: 0 !important;
  box-shadow: none !important;
  border-bottom: 1px solid #eee;
}

/* 覆盖 github-markdown-css 的一些样式以适应布局 */
.markdown-body {
  box-sizing: border-box;
  min-width: 200px;
  max-width: 980px;
  margin: 0 auto;
  padding: 15px;
}

@media (max-width: 768px) {
  .docs-layout {
    flex-direction: column;
  }
  .docs-sidebar {
    width: 100%;
    height: auto;
    position: static;
  }
}
</style>
